#!/usr/bin/python3
# -*- coding: utf-8 -*-
#
# Univention App Center
#  univention-app module for working with the Univention App Center Self Service
#
# Copyright 2016-2022 Univention GmbH
#
# http://www.univention.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# Binary versions of this program provided by Univention to you as
# well as other copyrighted, protected or trademarked materials like
# Logos, graphics, fonts, specific documentations and configurations,
# cryptographic keys etc. are subject to a license agreement between
# you and Univention and not subject to the GNU AGPL V3.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <http://www.gnu.org/licenses/>.
#

import json
import logging
import os.path
import re
import sys
from argparse import SUPPRESS, Action, ArgumentParser, Namespace
from contextlib import contextmanager
from distutils.version import LooseVersion
from getpass import getpass
from subprocess import PIPE, Popen
from tempfile import NamedTemporaryFile


PROGRAM = sys.argv[0]
if PROGRAM == '-':
	PROGRAM = 'univention-appcenter-control'


def get_base_logger():
	'''Returns the base logger for univention.appcenter'''
	return logging.getLogger('univention.appcenter')


class RangeFilter(logging.Filter):
	'''A Filter object that filters messages in a certain
	range of logging levels'''
	def __init__(self, min_level=None, max_level=None):
		super(RangeFilter, self).__init__()
		self.min_level = min_level
		self.max_level = max_level

	def filter(self, record):
		if self.max_level is None:
			return record.levelno >= self.min_level
		if self.min_level is None:
			return record.levelno <= self.max_level
		return self.min_level <= record.levelno <= self.max_level


def log_to_stream():
	'''Call this function to log to stdout/stderr
	stdout: logging.INFO
	stderr: logging.WARN and upwards
	logging.DEBUG: suppressed
	only the message is logged, no further formatting
	stderr is logged in red (if its a tty)
	'''
	if not log_to_stream._already_set_up:
		log_to_stream._already_set_up = True
		logger = get_base_logger()
		handler = logging.StreamHandler(sys.stdout)
		handler.addFilter(RangeFilter(min_level=logging.INFO, max_level=logging.INFO))
		logger.addHandler(handler)
		handler = logging.StreamHandler(sys.stderr)
		if sys.stderr.isatty():
			formatter = logging.Formatter('\x1b[1;31m%(message)s\x1b[0m')  # red
			handler.setFormatter(formatter)
		handler.addFilter(RangeFilter(min_level=logging.WARN))
		logger.addHandler(handler)


log_to_stream._already_set_up = False


def underscore(value):
	if value:
		return re.sub('([a-z])([A-Z])', r'\1_\2', value).lower()


_ACTIONS = {}


class Abort(Exception):
	pass


class UniventionAppActionMeta(type):
	def __new__(mcs, name, bases, attrs):
		new_cls = super(UniventionAppActionMeta, mcs).__new__(mcs, name, bases, attrs)
		if hasattr(new_cls, 'main') and getattr(new_cls, 'main') is not None:
			_ACTIONS[new_cls.get_action_name()] = new_cls
			new_cls.logger = new_cls.parent_logger.getChild(new_cls.get_action_name())
			new_cls.progress = new_cls.logger.getChild('progress')
		return new_cls


class UniventionAppAction(object, metaclass=UniventionAppActionMeta):

	parent_logger = get_base_logger().getChild('actions')

	def __init__(self):
		self._progress_percentage = 0

	@classmethod
	def get_action_name(cls):
		return underscore(cls.__name__).replace('_', '-')

	@classmethod
	def _log(cls, logger, level, msg, *args, **kwargs):
		if logger is not None:
			logger = cls.logger.getChild(logger)
		else:
			logger = cls.logger
		logger.log(level, msg, *args, **kwargs)

	@classmethod
	def debug(cls, msg, logger=None):
		cls._log(logger, logging.DEBUG, str(msg))

	@classmethod
	def log(cls, msg, logger=None):
		cls._log(logger, logging.INFO, str(msg))

	@classmethod
	def warn(cls, msg, logger=None):
		cls._log(logger, logging.WARN, str(msg))

	@classmethod
	def fatal(cls, msg, logger=None):
		cls._log(logger, logging.FATAL, str(msg))

	@classmethod
	def log_exception(cls, exc, logger=None):
		cls._log(logger, logging.ERROR, exc, exc_info=1)

	def setup_parser(self, parser):
		pass

	@property
	def percentage(self):
		return self._progress_percentage

	@percentage.setter
	def percentage(self, percentage):
		self._progress_percentage = percentage
		self.progress.debug(str(percentage))

	def _build_namespace(self, _namespace=None, **kwargs):
		parser = ArgumentParser()
		self.setup_parser(parser)
		namespace = Namespace()
		args = {}
		for action in parser._actions:
			default = parser._defaults.get(action.dest)
			if action.default is not None:
				default = action.default
			if hasattr(_namespace, action.dest):
				default = getattr(_namespace, action.dest)
			args[action.dest] = default
		args.update(kwargs)
		for key, value in args.items():
			setattr(namespace, key, value)
		return namespace

	@classmethod
	def call_safe(cls, **kwargs):
		try:
			return cls.call(**kwargs)
		except Abort:
			return None

	@classmethod
	def call(cls, **kwargs):
		obj = cls()
		namespace = obj._build_namespace(**kwargs)
		return obj.call_with_namespace(namespace)

	def call_with_namespace(self, namespace):
		self.debug('Calling %s' % self.get_action_name())
		self.percentage = 0
		try:
			result = self.main(namespace)
		except Abort as exc:
			msg = str(exc)
			if msg:
				self.fatal(msg)
			self.percentage = 100
			raise
		except Exception as exc:
			self.log_exception(exc)
			raise
		else:
			self.percentage = 100
			return result


class ConnectionFailed(Abort):
	pass


class ConnectionFailedSecretFile(ConnectionFailed):
	pass


class ConnectionFailedInvalidCredentials(ConnectionFailed):
	pass


class ConnectionFailedInvalidMachineCredentials(ConnectionFailedInvalidCredentials):
	pass


class ConnectionFailedInvalidUserCredentials(ConnectionFailedInvalidCredentials):
	pass


class ConnectionFailedServerDown(ConnectionFailed):
	pass


class CredentialsAction(UniventionAppAction):
	def __init__(self):
		super(CredentialsAction, self).__init__()
		self._username = None
		self._userdn = None
		self._password = None

	def setup_parser(self, parser):
		parser.add_argument('--noninteractive', action='store_true', help='Do not prompt for anything, just agree or skip')
		parser.add_argument('--username', default='Administrator', help='The username used for registering the app. Default: %(default)s')
		parser.add_argument('--pwdfile', help='Filename containing the password for registering the app. See --username')
		parser.add_argument('--password', help=SUPPRESS)

	def _get_username(self, args):
		if self._username is not None:
			return self._username
		if args.username:
			return args.username
		if not args.noninteractive:
			try:
				username = input('Username: ')
				if not username:
					raise EOFError()
			except (EOFError, KeyboardInterrupt):
				raise Abort()
			self._username = username
			return username

	def _get_password(self, args, ask=True):
		username = self._get_username(args)
		if not username:
			return None
		if self._password is not None:
			return self._password
		if args.password:
			return args.password
		if args.pwdfile:
			password = open(args.pwdfile, "r").read().rstrip('\n')
			return password
		if ask and not args.noninteractive:
			self._password = self._get_password_for(username)
		return self._password

	def _get_password_for(self, username):
		try:
			return getpass('Password for %s: ' % username)
		except (EOFError, KeyboardInterrupt):
			raise Abort()

	@contextmanager
	def _get_password_file(self, args=None, password=None):
		if password is None:
			password = self._get_password(args)
		if not password:
			yield None
		else:
			with NamedTemporaryFile('w+') as password_file:
				password_file.write(password)
				password_file.flush()
				yield password_file.name


class SelfserviceAction(CredentialsAction):
	print_commands = True
	API_LEVEL = 5

	def __init__(self):
		super(SelfserviceAction, self).__init__()
		self._username = None
		self._password = None

	def setup_parser(self, parser):
		try:
			with open(os.path.expanduser(os.path.join('~', '.univention-appcenter-user')), "r") as f:
				username = f.read().strip()
		except EnvironmentError:
			username = None
		pwdfile = os.path.expanduser(os.path.join('~', '.univention-appcenter-pwd'))
		if not os.path.exists(pwdfile):
			pwdfile = None
		parser.add_argument('--noninteractive', action='store_true', help='Do not prompt for anything, just agree or skip')
		parser.add_argument('--username', default=username, help='The username used for registering the app. Default: %(default)s')
		parser.add_argument('--pwdfile', default=pwdfile, help='Filename containing the password for registering the app. See --username')
		parser.add_argument('--password', help=SUPPRESS)
		parser.add_argument('--server', default='provider-portal.software-univention.de', help='The server to talk to')

	def _get_result(self, result):
		try:
			if result['status'] != 200:
				raise KeyError('result')
			return result['result']
		except KeyError:
			raise Abort('Unrecoverable result: %r' % result)

	def _login(self, args):
		self._username = self._get_username(args)
		self._password = self._get_password(args)
		result = self.command(args, 'api')
		remote_api_level = self._get_result(result)
		if remote_api_level != self.API_LEVEL:
			raise Abort('The Self Service has been updated (LEVEL=%s). Please update your script (LEVEL=%s)' % (remote_api_level, self.API_LEVEL))

	def curl(self, args, path, _command=False, **kwargs):
		server = args.server
		if not server.startswith('http'):
			server = 'https://%s' % server
		uri = '%s/univention/%s' % (server, path)
		args = []
		for key, value in kwargs.items():
			if value is None:
				continue
			if not isinstance(value, (tuple, list)):
				value = [value]
			for val in value:
				if _command:
					args.append('-d')
				else:
					args.append('-F')
				args.append('%s=%s' % (key, val))
		if self.print_commands:
			self.log('Curling %s' % uri)
		if not args:
			args.extend(['-X', 'POST'])
			args.extend(['-H', 'Content-Length: 0'])

		args = ['curl', '--basic', '--user', '%s:%s' % (self._username, self._password), '-H', 'X-Requested-With: XmlHttpRequest', '-H', 'Accept: application/json; q=1'] + args + [uri]
		process = Popen(args, stdout=PIPE, stderr=PIPE)
		out, err = process.communicate()
		out, err = out.decode('UTF-8'), err.decode('UTF-8')
		try:
			return json.loads(out)
		except ValueError:
			self.fatal('No JSON found. This looks like a server error (e.g., Apache in front of Univention Management Console)')
			self.log(out)
			raise Abort('Unrecoverable Response')

	def command(self, args, command, **kwargs):
		if not self._username:
			self._login(args)
		return self.curl(args, 'command/appcenter-selfservice/%s' % command, _command=True, **kwargs)

	def upload(self, args, **kwargs):
		if not self._username:
			self._login(args)
		return self.curl(args, 'upload/appcenter-selfservice/upload', **kwargs)


class StoreAppAction(Action):
	@classmethod
	def parse_app_id_string(cls, app_id):
		if app_id is None:
			return None, None, None, None
		try:
			app_id, app_version = app_id.split('=', 1)
		except ValueError:
			app_id, app_version = app_id, None
		try:
			ucs_version, app_id = app_id.split('/', 1)
		except ValueError:
			ucs_version, app_id = None, app_id
		if ucs_version:
			try:
				ucs_version, server = ucs_version.split('@', 1)
			except ValueError:
				ucs_version, server = ucs_version, None
		else:
			server = None
		ucs_version = ucs_version or None
		return app_id, app_version, ucs_version, server

	def __call__(self, parser, namespace, value, option_string=None):
		apps = []
		if self.nargs is None or self.nargs == '?':
			value = [value]
		for val in value:
			app_id, app_version, ucs_version, server = self.parse_app_id_string(val)
			app = app_id, app_version, ucs_version, server
			apps.append(app)
		if self.nargs is None:
			apps = apps[0]
		setattr(namespace, self.dest, apps)


class SelfserviceAppAction(SelfserviceAction):
	def setup_parser(self, parser):
		super(SelfserviceAppAction, self).setup_parser(parser)
		parser.add_argument('app', action=StoreAppAction, help='The App: [UCS_VERSION/]APP_ID[=APP_VERSION]. Optional params do not always make sense.')

	def _get_ucs_version(self, app):
		__, __, ucs_version, __ = app
		return ucs_version or '4.1'

	def _find_app(self, args):
		__, app_version, __, __ = args.app
		versions = self._find_app_versions(args)
		maybe_apps = []
		for app in versions:
			if app_version is None:
				maybe_apps.append((LooseVersion(app['version']), app))
			else:
				if app['version'] == app_version:
					return app
		if maybe_apps:
			return sorted(maybe_apps)[-1][-1]
		raise Abort('Could not find App %r' % (tuple(args.app),))

	def _find_all_app_versions(self, args):
		app_id, __, __, __ = args.app
		apps = self._get_result(self.command(args, 'query'))
		ret = []
		for app in apps:
			if app['id'] == app_id:
				ret.extend(app['versions'])
		return ret

	def _find_app_versions(self, args):
		ucs_version = self._get_ucs_version(args.app)
		versions = self._find_all_app_versions(args)
		return [version for version in versions if version['ucs_version'] == ucs_version]


class List(SelfserviceAction):
	'''List all Apps'''
	help = 'Lists all Apps'

	def setup_parser(self, parser):
		super(List, self).setup_parser(parser)
		parser.add_argument('--json', action='store_true', help='If set to yes, output is JSON and as such, easily parsable')

	def main(self, args):
		if args.json:
			self.print_commands = False
		result = self._get_result(self.command(args, 'query'))
		if args.json:
			self.output_json(result)
		else:
			self.output_text(result)

	def output_json(self, result):
		res = {}
		vendor_ids = {app['vendor'] for app in result}
		for vendor_id in sorted(vendor_ids, key=lambda vendor: vendor.lower()):
			apps = [app for app in result if app['vendor'] == vendor_id]
			res[vendor_id] = apps
			for app in apps:
				app.pop('base64_logo', None)
		self.log(json.dumps(res, indent=2, sort_keys=True))

	def output_text(self, result):
		vendor_ids = {app['vendor'] for app in result}
		for vendor_id in sorted(vendor_ids, key=lambda vendor: vendor.lower()):
			self.log('')
			self.log(vendor_id)
			apps = [app for app in result if app['vendor'] == vendor_id]
			for app in apps:
				self.log('  %s/%s=%s' % (app['ucs_version'], app['id'], app['version']))


class Status(SelfserviceAppAction):
	'''Fetch status of an App'''
	help = 'Lists available versions, their status, etc. in the Univention App Center Provider Portal'

	def main(self, args):
		apps = self._find_all_app_versions(args)
		for app_version in apps:
			self.log('')
			appcenter_status = 'Draft'
			if app_version.get('in_appcenter'):
				appcenter_status = 'Published'
			self.log('%s/%s=%s' % (app_version['ucs_version'], app_version['id'], app_version['version']))
			self.log('   COMPONENT: %s' % app_version['component_id'])
			self.log('      STATUS: %s' % appcenter_status)


class NewVersion(SelfserviceAppAction):
	'''Copy an existing App to a new UCS version or to become a new App version.'''
	help = 'Copy an App'

	def setup_parser(self, parser):
		super(NewVersion, self).setup_parser(parser)
		parser.add_argument('new_app', nargs='?', action=StoreAppAction, help='The new App: UCS_VERSION/APP_ID=APP_VERSION. UCS_VERSION and APP_VERSION are important for the new version to be created. APP_ID is not considered.')
		parser.add_argument('--new-component', help='Component of the new App. If not given, a new one will be created. Useful when juggling with Apps in multiple UCS versions.')

	def main(self, args):
		return self.new_version(args)

	def new_version(self, args):
		app = self._find_app(args)
		component_id = app['component_id']
		app_version = app['version']
		ucs_version = app['ucs_version']

		new_app = args.new_app[0]
		__, new_app_version, new_ucs_version, __ = new_app
		new_ucs_version = new_ucs_version or ucs_version
		if new_ucs_version == ucs_version and new_app_version is None:
			match = re.search(r'(.*) ucs-(\d+)$', app_version)
			if match:
				plain_version, ucs_part = match.groups()
				new_app_version = '%s ucs-%d' % (plain_version, int(ucs_part) + 1)
			else:
				new_app_version = '%s ucs-1' % app_version
		result = self.command(args, 'copy', ucs_version=ucs_version, component_id=component_id, new_ucs_version=new_ucs_version, new_app_version=new_app_version, new_component=args.new_component)
		new_app = self._get_result(result)
		self.log('New version for %s:' % app['id'])
		self.log('  %s/%s=%s' % (new_app['ucs_version'], new_app['id'], new_app['version']))
		return new_app


class RemoveVersion(SelfserviceAppAction):
	'''Remove an existing app version'''
	help = 'Remove an app version'

	def main(self, args):
		return self.remove_version(args)

	def remove_version(self, args):
		app = self._find_app(args)
		component_id = app['component_id']
		app_version = app['version']
		ucs_version = app['ucs_version']

		result = self._get_result(self.command(args, 'remove', ucs_version=ucs_version, component_id=component_id))
		self.log('Removed %s/%s' % (app['id'], app['ucs_version']))
		return result


class Upload(SelfserviceAppAction):
	'''Upload an App'''
	help = 'Uploads an App to the Univention App Center Self Service'

	UPLOAD_LIMIT = 1024 * 1024 * 250

	def setup_parser(self, parser):
		super(Upload, self).setup_parser(parser)
		parser.add_argument('--dont-clear', action='store_true', help='Clears all packages with the same name (but a different version) as the uploaded packages. Only works for "deb" (and deb in "tar.gz") uploads')
		parser.add_argument('--upload-packages-although-published', action='store_true', help=SUPPRESS)  # Does not work
		parser.add_argument('uploads', nargs='+', help='List of files to upload. For most files, they need to be named after their type, or have it as extension. Images / Logos need to be named exactly as in the ini file. Example: "README_EN"; "myapp.ini"; "app.tar.gz"; "my-screenshot.png"')

	def main(self, args):
		files = []
		upload_size = 0
		for upload in args.uploads:
			upload = os.path.abspath(upload)
			if not os.path.exists(upload):
				self.warn('%s does not exist! Skipping...' % upload)
				continue
			file_size = os.stat(upload).st_size
			if upload_size + file_size > self.UPLOAD_LIMIT:
				if not files:
					self.warn('%s is too big. We can only upload files up to %d bytes' % (upload, self.UPLOAD_LIMIT))
					return False
				self.upload_files(args, files)
				self.log('Done uploading %d file(s). Continuing...' % len(files))
				files[:] = []
				upload_size = 0
			upload_size += file_size
			self.log('Uploading %s' % upload)
			files.append(upload)
		if files:
			self.upload_files(args, files)
			self.log('Finished uploading.')

	def upload_files(self, args, files):
		app = self._find_app(args)
		component_id = app['component_id']
		ucs_version = app['ucs_version']
		clear = str(not args.dont_clear).lower()
		force = str(args.upload_packages_although_published).lower()
		result = self.upload(args, ucs_version=ucs_version, component_id=component_id, force=force, clear=clear, filename=['@%s' % fname for fname in files])
		self._get_result(result)


class Get(SelfserviceAppAction):
	'''Gets attributes and/or file contents of App. NOTE: The name of the keys and the semantics of the values are quite internal. If you have questions, ask appcenter@univention.de.'''
	help = 'Get attributes of an App'
	print_commands = False

	def setup_parser(self, parser):
		super(Get, self).setup_parser(parser)
		changes_format = parser.add_mutually_exclusive_group(required=True)
		changes_format.add_argument('--json', action='store_true', help='Format is JSON. Example: %s get myapp=1.0 --json | jq -r .name' % PROGRAM)

	def main(self, args):
		app = self._find_app(args)
		result = self.command(args, 'get', **app)
		attributes = self._get_result(result)
		if args.json:
			self.log(json.dumps(attributes, indent=2, sort_keys=True))


class Set(SelfserviceAppAction):
	'''Changes attributes and/or file contents of App. NOTE: The name of the keys and the semantics of the values are quite internal. If you have questions, ask appcenter@univention.de. You can also use the "get" subcommand to get an idea how the input should look like. A value of null normally deletes the entry.'''
	help = 'Set attributes of an App'

	def setup_parser(self, parser):
		super(Set, self).setup_parser(parser)
		parser.add_argument('changes', help='Apply these CHANGES to the APP')
		changes_format = parser.add_mutually_exclusive_group(required=True)
		changes_format.add_argument('--json', action='store_true', help='Format is JSON. Example: %s set myapp=1.0 --json \'{"version": "1.1", "docker_image": "myimage:1.1"}\'' % PROGRAM)

	def _get_changes_dict(self, args):
		if args.json:
			try:
				value = json.loads(args.changes)
				if not isinstance(value, dict):
					raise TypeError(value)
			except (TypeError, ValueError):
				raise Abort('Unable to parse CHANGES as a JSON dict')
			else:
				return value
		else:
			raise Abort('Unknown format given. Please provide something the script can understand and then send to the App Provider Portal.')

	def main(self, args):
		changes = self._get_changes_dict(args)
		app = self._find_app(args)
		changes['component_id'] = app['component_id']
		changes['ucs_version'] = app['ucs_version']
		result = self.command(args, 'save', **changes)
		self._get_result(result)
		self.log('Finished setting new value')


def get_action(action_name):
	return _ACTIONS.get(action_name)


def all_actions():
	for action_name in sorted(_ACTIONS):
		yield action_name, _ACTIONS[action_name]


def add_action(subparsers, action):
	description = action.__doc__ or action.help
	help = action.help or action.__doc__
	subparser = subparsers.add_parser(action.get_action_name(), description=description, help=help)
	action.setup_parser(subparser)
	subparser.set_defaults(func=action.call_with_namespace)
	return subparser


def main():
	usage = PROGRAM
	description = '%s is a program to use the Univention App Center Self Service' % PROGRAM
	parser = ArgumentParser(usage=usage, description=description)
	subparsers = parser.add_subparsers(description='type %s <action> --help for further help and possible arguments' % PROGRAM, metavar='action')

	get_base_logger().setLevel(logging.DEBUG)
	get_base_logger().addHandler(logging.NullHandler())  # this is to prevent warning messages
	log_to_stream()

	for action_name, action in all_actions():
		add_action(subparsers, action())

	args = parser.parse_args()

	try:
		ret = args.func(args)
	except Abort:
		ret = 10
	if ret is True:
		ret = 0
	elif ret is False:
		ret = 1
	elif not isinstance(ret, int):
		ret = 0
	sys.exit(ret)


if __name__ == '__main__':
	main()