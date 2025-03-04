# Copyright 2014 Pants project contributors (see CONTRIBUTORS.md).
# Licensed under the Apache License, Version 2.0 (see LICENSE).

import multiprocessing
import os
import sys
from dataclasses import dataclass
from typing import Any

from pants.base.build_environment import (
  get_buildroot,
  get_default_pants_config_file,
  get_pants_cachedir,
  get_pants_configdir,
  pants_version,
)
from pants.option.arg_splitter import GLOBAL_SCOPE
from pants.option.custom_types import dir_option, file_option
from pants.option.errors import OptionsError
from pants.option.optionable import Optionable
from pants.option.scope import ScopeInfo
from pants.subsystem.subsystem_client_mixin import SubsystemClientMixin
from pants.util.collections import Enum


class GlobMatchErrorBehavior(Enum):
  """Describe the action to perform when matching globs in BUILD files to source files.

  NB: this object is interpreted from within Snapshot::lift_path_globs() -- that method will need to
  be aware of any changes to this object's definition.
  """
  ignore = "ignore"
  warn = "warn"
  error = "error"


@dataclass(frozen=True)
class ExecutionOptions:
  """A collection of all options related to (remote) execution of processes.

  TODO: These options should move to a Subsystem once we add support for "bootstrap" Subsystems (ie,
  allowing Subsystems to be consumed before the Scheduler has been created).
  """
  remote_execution: Any
  remote_store_server: Any
  remote_store_thread_count: Any
  remote_execution_server: Any
  remote_store_chunk_bytes: Any
  remote_store_chunk_upload_timeout_seconds: Any
  remote_store_rpc_retries: Any
  remote_store_connection_limit: Any
  process_execution_local_parallelism: Any
  process_execution_remote_parallelism: Any
  process_execution_cleanup_local_dirs: Any
  process_execution_speculation_delay: Any
  process_execution_speculation_strategy: Any
  process_execution_use_local_cache: Any
  remote_execution_process_cache_namespace: Any
  remote_instance_name: Any
  remote_ca_certs_path: Any
  remote_oauth_bearer_token_path: Any
  remote_execution_extra_platform_properties: Any
  remote_execution_headers: Any

  @classmethod
  def from_bootstrap_options(cls, bootstrap_options):
    return cls(
      remote_execution=bootstrap_options.remote_execution,
      remote_store_server=bootstrap_options.remote_store_server,
      remote_execution_server=bootstrap_options.remote_execution_server,
      remote_store_thread_count=bootstrap_options.remote_store_thread_count,
      remote_store_chunk_bytes=bootstrap_options.remote_store_chunk_bytes,
      remote_store_chunk_upload_timeout_seconds=bootstrap_options.remote_store_chunk_upload_timeout_seconds,
      remote_store_rpc_retries=bootstrap_options.remote_store_rpc_retries,
      remote_store_connection_limit=bootstrap_options.remote_store_connection_limit,
      process_execution_local_parallelism=bootstrap_options.process_execution_local_parallelism,
      process_execution_remote_parallelism=bootstrap_options.process_execution_remote_parallelism,
      process_execution_cleanup_local_dirs=bootstrap_options.process_execution_cleanup_local_dirs,
      process_execution_speculation_delay=bootstrap_options.process_execution_speculation_delay,
      process_execution_speculation_strategy=bootstrap_options.process_execution_speculation_strategy,
      process_execution_use_local_cache=bootstrap_options.process_execution_use_local_cache,
      remote_execution_process_cache_namespace=bootstrap_options.remote_execution_process_cache_namespace,
      remote_instance_name=bootstrap_options.remote_instance_name,
      remote_ca_certs_path=bootstrap_options.remote_ca_certs_path,
      remote_oauth_bearer_token_path=bootstrap_options.remote_oauth_bearer_token_path,
      remote_execution_extra_platform_properties=bootstrap_options.remote_execution_extra_platform_properties,
      remote_execution_headers=bootstrap_options.remote_execution_headers,
    )


DEFAULT_EXECUTION_OPTIONS = ExecutionOptions(
    remote_execution=False,
    remote_store_server=[],
    remote_store_thread_count=1,
    remote_execution_server=None,
    remote_store_chunk_bytes=1024*1024,
    remote_store_chunk_upload_timeout_seconds=60,
    remote_store_rpc_retries=2,
    remote_store_connection_limit=5,
    process_execution_local_parallelism=multiprocessing.cpu_count()*2,
    process_execution_remote_parallelism=128,
    process_execution_cleanup_local_dirs=True,
    process_execution_speculation_delay=1,
    process_execution_speculation_strategy='local_first',
    process_execution_use_local_cache=True,
    remote_execution_process_cache_namespace=None,
    remote_instance_name=None,
    remote_ca_certs_path=None,
    remote_oauth_bearer_token_path=None,
    remote_execution_extra_platform_properties=[],
    remote_execution_headers={},
  )


class GlobalOptionsRegistrar(SubsystemClientMixin, Optionable):
  options_scope = GLOBAL_SCOPE
  options_scope_category = ScopeInfo.GLOBAL

  @classmethod
  def register_bootstrap_options(cls, register):
    """Register bootstrap options.

    "Bootstrap options" are a small set of options whose values are useful when registering other
    options. Therefore we must bootstrap them early, before other options are registered, let
    alone parsed.

    Bootstrap option values can be interpolated into the config file, and can be referenced
    programatically in registration code, e.g., as register.bootstrap.pants_workdir.

    Note that regular code can also access these options as normal global-scope options. Their
    status as "bootstrap options" is only pertinent during option registration.
    """
    buildroot = get_buildroot()
    default_distdir_name = 'dist'
    default_rel_distdir = f'/{default_distdir_name}/'

    register('-l', '--level', choices=['trace', 'debug', 'info', 'warn'], default='info',
             recursive=True, help='Set the logging level.')
    register('-q', '--quiet', type=bool, recursive=True, daemon=False,
             help='Squelches most console output. NOTE: Some tasks default to behaving quietly: '
                  'inverting this option supports making them noisier than they would be otherwise.')
    register('--log-show-rust-3rdparty', type=bool, default=False, advanced=True,
             help='Whether to show/hide logging done by 3rdparty rust crates used by the pants '
                  'engine.')

    # Not really needed in bootstrap options, but putting it here means it displays right
    # after -l and -q in help output, which is conveniently contextual.
    register('--colors', type=bool, default=sys.stdout.isatty(), recursive=True, daemon=False,
             help='Set whether log messages are displayed in color.')
    # TODO(#7203): make a regexp option type!
    register('--ignore-pants-warnings', type=list, member_type=str, default=[],
             help='Regexps matching warning strings to ignore, e.g. '
                  '["DEPRECATED: scope some_scope will be removed"]. The regexps will be matched '
                  'from the start of the warning string, and will always be case-insensitive. '
                  'See the `warnings` module documentation for more background on these are used.')
    register('--option-name-check-distance', advanced=True, type=int, default=2,
             help='The maximum Levenshtein distance to use when offering suggestions for invalid '
                  'option names.')

    register('--pants-version', advanced=True, default=pants_version(),
             help='Use this pants version. Note Pants code only uses this to verify that you are '
                  'using the requested version, as Pants cannot dynamically change the version it '
                  'is using once the program is already running. This option is useful to set in '
                  'your pants.ini, however, and then you can grep the value to select which '
                  'version to use for setup scripts (e.g. `./pants`), runner scripts, IDE plugins, '
                  'etc. For example, the setup script we distribute at https://www.pantsbuild.org/install.html#recommended-installation '
                  'uses this value to determine which Python version to run with. You may find the '
                  'version of the pants instance you are running using -v, -V, or --version.')

    register('--plugins', advanced=True, type=list, help='Load these plugins.')
    register('--plugin-cache-dir', advanced=True,
             default=os.path.join(get_pants_cachedir(), 'plugins'),
             help='Cache resolved plugin requirements here.')

    register('--backend-packages', advanced=True, type=list,
             default=['pants.backend.graph_info',
                      'pants.backend.python',
                      'pants.backend.jvm',
                      'pants.backend.native',
                      'pants.backend.codegen.antlr.java',
                      'pants.backend.codegen.antlr.python',
                      'pants.backend.codegen.jaxb',
                      'pants.backend.codegen.protobuf.java',
                      'pants.backend.codegen.ragel.java',
                      'pants.backend.codegen.thrift.java',
                      'pants.backend.codegen.thrift.python',
                      'pants.backend.codegen.grpcio.python',
                      'pants.backend.codegen.wire.java',
                      'pants.backend.project_info'],
             help='Load backends from these packages that are already on the path. '
                  'Add contrib and custom backends to this list.')

    register('--pants-bootstrapdir', advanced=True, metavar='<dir>', default=get_pants_cachedir(),
             help='Use this dir for global cache.')
    register('--pants-configdir', advanced=True, metavar='<dir>', default=get_pants_configdir(),
             help='Use this dir for global config files.')
    register('--pants-workdir', advanced=True, metavar='<dir>',
             default=os.path.join(buildroot, '.pants.d'),
             help='Write intermediate output files to this dir.')
    register('--pants-physical-workdir-base', advanced=True, metavar='<dir>',
             default=None,
             help='When set, a base directory in which to store `--pants-workdir` contents. '
                  'If this option is a set, the workdir will be created as symlink into a '
                  'per-workspace subdirectory.')
    register('--pants-supportdir', advanced=True, metavar='<dir>',
             default=os.path.join(buildroot, 'build-support'),
             help='Use support files from this dir.')
    register('--pants-distdir', advanced=True, metavar='<dir>',
             default=os.path.join(buildroot, 'dist'),
             help='Write end-product artifacts to this dir.')
    register('--pants-subprocessdir', advanced=True, default=os.path.join(buildroot, '.pids'),
             help='The directory to use for tracking subprocess metadata, if any. This should '
                  'live outside of the dir used by `--pants-workdir` to allow for tracking '
                  'subprocesses that outlive the workdir data (e.g. `./pants server`).')
    register('--pants-config-files', advanced=True, type=list, daemon=False,
             default=[get_default_pants_config_file()], help='Paths to Pants config files.')
    # TODO: Deprecate the --pantsrc/--pantsrc-files options?  This would require being able
    # to set extra config file locations in an initial bootstrap config file.
    register('--pantsrc', advanced=True, type=bool, default=True,
             help='Use pantsrc files.')
    register('--pantsrc-files', advanced=True, type=list, metavar='<path>', daemon=False,
             default=['/etc/pantsrc', '~/.pants.rc'],
             help='Override config with values from these files. '
                  'Later files override earlier ones.')
    register('--pythonpath', advanced=True, type=list,
             help='Add these directories to PYTHONPATH to search for plugins.')
    register('--target-spec-file', type=list, dest='target_spec_files', daemon=False,
             help='Read additional specs from this file, one per line')
    register('--verify-config', type=bool, default=True, daemon=False,
             advanced=True,
             help='Verify that all config file values correspond to known options.')

    register('--build-ignore', advanced=True, type=list,
             default=['.*/', 'bower_components/',
                      'node_modules/', '*.egg-info/'],
             help='Paths to ignore when identifying BUILD files. '
                  'This does not affect any other filesystem operations. '
                  'Patterns use the gitignore pattern syntax (https://git-scm.com/docs/gitignore).')
    register('--pants-ignore', advanced=True, type=list,
             default=['.*/', default_rel_distdir],
             help='Paths to ignore for all filesystem operations performed by pants '
                  '(e.g. BUILD file scanning, glob matching, etc). '
                  'Patterns use the gitignore syntax (https://git-scm.com/docs/gitignore). '
                  'The `--pants-distdir` and `--pants-workdir` locations are inherently ignored.')
    register('--glob-expansion-failure', advanced=True,
             default=GlobMatchErrorBehavior.warn, type=GlobMatchErrorBehavior,
             help="Raise an exception if any targets declaring source files "
                  "fail to match any glob provided in the 'sources' argument.")

    # TODO(#7203): make a regexp option type!
    register('--exclude-target-regexp', advanced=True, type=list, default=[], daemon=False,
             metavar='<regexp>', help='Exclude target roots that match these regexes.')
    register('--subproject-roots', type=list, advanced=True, default=[],
             help='Paths that correspond with build roots for any subproject that this '
                  'project depends on.')
    register('--owner-of', type=list, member_type=file_option, default=[], daemon=False, metavar='<path>',
             help='Select the targets that own these files. '
                  'This is the third target calculation strategy along with the --changed-* '
                  'options and specifying the targets directly. These three types of target '
                  'selection are mutually exclusive.')

    # These logging options are registered in the bootstrap phase so that plugins can log during
    # registration and not so that their values can be interpolated in configs.
    register('-d', '--logdir', advanced=True, metavar='<dir>',
             help='Write logs to files under this directory.')

    # This facilitates bootstrap-time configuration of pantsd usage such that we can
    # determine whether or not to use the Pailgun client to invoke a given pants run
    # without resorting to heavier options parsing.
    register('--enable-pantsd', advanced=True, type=bool, default=False,
             help='Enables use of the pants daemon (and implicitly, the v2 engine). (Beta)')

    # Whether or not to make necessary arrangements to have concurrent runs in pants.
    # In practice, this means that if this is set, a run will not even try to use pantsd.
    # NB: Eventually, we would like to deprecate this flag in favor of making pantsd runs parallelizable.
    register('--concurrent', advanced=True, type=bool, default=False, daemon=False,
             help='Enable concurrent runs of pants. Without this enabled, pants will '
                  'start up all concurrent invocations (e.g. in other terminals) without pantsd. '
                  'Enabling this option requires parallel pants invocations to block on the first')

    # Shutdown pantsd after the current run.
    # This needs to be accessed at the same time as enable_pantsd,
    # so we register it at bootstrap time.
    register('--shutdown-pantsd-after-run', advanced=True, type=bool, default=False,
      help='Create a new pantsd server, and use it, and shut it down immediately after. '
           'If pantsd is already running, it will shut it down and spawn a new instance (Beta)')

    # NB: We really don't want this option to invalidate the daemon, because different clients might have
    # different needs. For instance, an IDE might have a very long timeout because it only wants to refresh
    # a project in the background, while a user might want a shorter timeout for interactivity.
    register('--pantsd-timeout-when-multiple-invocations', advanced=True, type=float, default=60.0, daemon=False,
             help='The maximum amount of time to wait for the invocation to start until '
                  'raising a timeout exception. '
                  'Because pantsd currently does not support parallel runs, '
                  'any prior running Pants command must be finished for the current one to start. '
                  'To never timeout, use the value -1.')

    # These facilitate configuring the native engine.
    register('--native-engine-visualize-to', advanced=True, default=None, type=dir_option, daemon=False,
             help='A directory to write execution and rule graphs to as `dot` files. The contents '
                  'of the directory will be overwritten if any filenames collide.')
    register('--print-exception-stacktrace', advanced=True, type=bool,
             help='Print to console the full exception stack trace if encountered.')

    # BinaryUtil options.
    register('--binaries-baseurls', type=list, advanced=True,
             default=['https://binaries.pantsbuild.org'],
             help='List of URLs from which binary tools are downloaded. URLs are '
                  'searched in order until the requested path is found.')
    register('--binaries-fetch-timeout-secs', type=int, default=30, advanced=True, daemon=False,
             help='Timeout in seconds for URL reads when fetching binary tools from the '
                  'repos specified by --baseurls.')
    register('--binaries-path-by-id', type=dict, advanced=True,
             help=("Maps output of uname for a machine to a binary search path: "
                   "(sysname, id) -> (os, arch), e.g. {('darwin', '15'): ('mac', '10.11'), "
                   "('linux', 'arm32'): ('linux', 'arm32')}."))
    register('--allow-external-binary-tool-downloads', type=bool, default=True, advanced=True,
             help="If False, require BinaryTool subclasses to download their contents from urls "
                  "generated from --binaries-baseurls, even if the tool has an external url "
                  "generator. This can be necessary if using Pants in an environment which cannot "
                  "contact the wider Internet.")

    # Pants Daemon options.
    register('--pantsd-pailgun-host', advanced=True, default='127.0.0.1',
             help='The host to bind the pants nailgun server to.')
    register('--pantsd-pailgun-port', advanced=True, type=int, default=0,
             help='The port to bind the pants nailgun server to. Defaults to a random port.')
    # TODO(#7514): Make this default to 1.0 seconds if stdin is a tty!
    register('--pantsd-pailgun-quit-timeout', advanced=True, type=float, default=5.0,
             help='The length of time (in seconds) to wait for further output after sending a '
                  'signal to the remote pantsd process before killing it.')
    register('--pantsd-log-dir', advanced=True, default=None,
             help='The directory to log pantsd output to.')
    register('--pantsd-invalidation-globs', advanced=True, type=list, default=[],
             help='Filesystem events matching any of these globs will trigger a daemon restart. '
                  'The `--pythonpath` and `--pants-config-files` are inherently invalidated.')

    # Watchman options.
    register('--watchman-version', advanced=True, default='4.9.0-pants1', help='Watchman version.')
    register('--watchman-supportdir', advanced=True, default='bin/watchman',
             help='Find watchman binaries under this dir. Used as part of the path to lookup '
                  'the binary with --binaries-baseurls and --pants-bootstrapdir.')
    register('--watchman-startup-timeout', type=float, advanced=True, default=30.0,
             help='The watchman socket timeout (in seconds) for the initial `watch-project` command. '
                  'This may need to be set higher for larger repos due to watchman startup cost.')
    register('--watchman-socket-timeout', type=float, advanced=True, default=0.1,
             help='The watchman client socket timeout in seconds. Setting this to too high a '
                  'value can negatively impact the latency of runs forked by pantsd.')
    register('--watchman-socket-path', type=str, advanced=True, default=None,
             help='The path to the watchman UNIX socket. This can be overridden if the default '
                  'absolute path length exceeds the maximum allowed by the OS.')

    # This option changes the parser behavior in a fundamental way (which currently invalidates
    # all caches), and needs to be parsed out early, so we make it a bootstrap option.
    register('--build-file-imports', choices=['allow', 'warn', 'error'], default='warn',
             advanced=True,
             help='Whether to allow import statements in BUILD files')

    register('--local-store-dir', advanced=True,
             help="Directory to use for engine's local file store.",
             # This default is also hard-coded into the engine's rust code in
             # fs::Store::default_path
             default=os.path.expanduser('~/.cache/pants/lmdb_store'))

    register('--remote-execution', advanced=True, type=bool,
             default=DEFAULT_EXECUTION_OPTIONS.remote_execution,
             help="Enables remote workers for increased parallelism. (Alpha)")
    register('--remote-store-server', advanced=True, type=list, default=[],
             help='host:port of grpc server to use as remote execution file store.')
    # TODO: Infer this from remote-store-connection-limit.
    register('--remote-store-thread-count', type=int, advanced=True,
             default=DEFAULT_EXECUTION_OPTIONS.remote_store_thread_count,
             help='Thread count to use for the pool that interacts with the remote file store.')
    register('--remote-execution-server', advanced=True,
             help='host:port of grpc server to use as remote execution scheduler.')
    register('--remote-store-chunk-bytes', type=int, advanced=True,
             default=DEFAULT_EXECUTION_OPTIONS.remote_store_chunk_bytes,
             help='Size in bytes of chunks transferred to/from the remote file store.')
    register('--remote-store-chunk-upload-timeout-seconds', type=int, advanced=True,
             default=DEFAULT_EXECUTION_OPTIONS.remote_store_chunk_upload_timeout_seconds,
             help='Timeout (in seconds) for uploads of individual chunks to the remote file store.')
    register('--remote-store-rpc-retries', type=int, advanced=True,
             default=DEFAULT_EXECUTION_OPTIONS.remote_store_rpc_retries,
             help='Number of times to retry any RPC to the remote store before giving up.')
    register('--remote-store-connection-limit', type=int, advanced=True,
             default=DEFAULT_EXECUTION_OPTIONS.remote_store_connection_limit,
             help='Number of remote stores to concurrently allow connections to.')
    register('--remote-execution-process-cache-namespace', advanced=True,
             help="The cache namespace for remote process execution. "
                  "Bump this to invalidate every artifact's remote execution. "
                  "This is the remote execution equivalent of the legacy cache-key-gen-version "
                  "flag.")
    register('--remote-instance-name', advanced=True,
             help='Name of the remote execution instance to use. Used for routing within '
                  '--remote-execution-server and --remote-store-server.')
    register('--remote-ca-certs-path', advanced=True,
             help='Path to a PEM file containing CA certificates used for verifying secure '
                  'connections to --remote-execution-server and --remote-store-server. '
                  'If not specified, TLS will not be used.')
    register('--remote-oauth-bearer-token-path', advanced=True,
             help='Path to a file containing an oauth token to use for grpc connections to '
                  '--remote-execution-server and --remote-store-server. If not specified, no '
                  'authorization will be performed.')
    register('--remote-execution-extra-platform-properties', advanced=True,
             help='Platform properties to set on remote execution requests. '
                  'Format: property=value. Multiple values should be specified as multiple '
                  'occurrences of this flag. Pants itself may add additional platform properties.',
                   type=list, default=[])
    register('--remote-execution-headers', advanced=True,
             help='Headers to set on remote execution requests. '
                  'Format: header=value. Pants itself may add additional headers.',
             type=dict, default={})
    register('--process-execution-local-parallelism', type=int, default=DEFAULT_EXECUTION_OPTIONS.process_execution_local_parallelism,
             advanced=True,
             help='Number of concurrent processes that may be executed locally.')
    register('--process-execution-remote-parallelism', type=int, default=DEFAULT_EXECUTION_OPTIONS.process_execution_remote_parallelism,
             advanced=True,
             help='Number of concurrent processes that may be executed remotely.')
    register('--process-execution-cleanup-local-dirs', type=bool, default=True, advanced=True,
             help='Whether or not to cleanup directories used for local process execution '
                  '(primarily useful for e.g. debugging).')
    register('--process-execution-speculation-delay', type=float,
             default=DEFAULT_EXECUTION_OPTIONS.process_execution_speculation_delay, advanced=True,
             help='Number of seconds to wait before speculating a second request for a slow process. '
                  ' see `--process-execution-speculation-strategy`')
    register('--process-execution-speculation-strategy', choices=['remote_first', 'local_first', 'none'],
             default=DEFAULT_EXECUTION_OPTIONS.process_execution_speculation_strategy,
             help="Speculate a second request for an underlying process if the first one does not complete within "
                  '`--process-execution-speculation-delay` seconds.\n'
                  '`local_first` (default): Try to run the process locally first, '
                  'and fall back to remote execution if available.\n'
                  '`remote_first`: Run the process on the remote execution backend if available, '
                  'and fall back to the local host if remote calls take longer than the speculation timeout.\n'
                  '`none`: Do not speculate about long running processes.',
             advanced=True)
    register('--process-execution-use-local-cache', type=bool, default=True, advanced=True,
             help='Whether to keep process executions in a local cache persisted to disk.')

  @classmethod
  def register_options(cls, register):
    """Register options not tied to any particular task or subsystem."""
    # The bootstrap options need to be registered on the post-bootstrap Options instance, so it
    # won't choke on them on the command line, and also so we can access their values as regular
    # global-scope options, for convenience.
    cls.register_bootstrap_options(register)

    register('-x', '--time', type=bool,
             help='Output a timing report at the end of the run.')
    register('-e', '--explain', type=bool,
             help='Explain the execution of goals.')
    register('--tag', type=list, metavar='[+-]tag1,tag2,...',
             help="Include only targets with these tags (optional '+' prefix) or without these "
                  "tags ('-' prefix).  Useful with ::, to find subsets of targets "
                  "(e.g., integration tests.)")

    # Toggles v1/v2 `Task` vs `@rule` pipelines on/off.
    register('--v1', advanced=True, type=bool, default=True,
             help='Enables execution of v1 Tasks.')
    register('--v2', advanced=True, type=bool, default=False,
             help='Enables execution of v2 @console_rules.')
    register('--v2-ui', default=False, type=bool, daemon=False,
             help='Whether to show v2 engine execution progress. '
                  'This requires the --v2 flag to take effect.')

    loop_flag = '--loop'
    register(loop_flag, type=bool,
             help='Run v2 @console_rules continuously as file changes are detected. Requires '
                  '`--v2`, and is best utilized with `--v2 --no-v1`.')
    register('--loop-max', type=int, default=2**32, advanced=True,
             help='The maximum number of times to loop when `{}` is specified.'.format(loop_flag))

    register('-t', '--timeout', advanced=True, type=int, metavar='<seconds>',
             help='Number of seconds to wait for http connections.')
    # TODO: After moving to the new options system these abstraction leaks can go away.
    register('-k', '--kill-nailguns', advanced=True, type=bool,
             help='Kill nailguns before exiting')
    register('--fail-fast', advanced=True, type=bool, recursive=True,
             help='Exit as quickly as possible on error, rather than attempting to continue '
                  'to process the non-erroneous subset of the input.')
    register('--cache-key-gen-version', advanced=True, default='200', recursive=True,
             help='The cache key generation. Bump this to invalidate every artifact for a scope.')
    register('--workdir-max-build-entries', advanced=True, type=int, default=8,
             help='Maximum number of previous builds to keep per task target pair in workdir. '
             'If set, minimum 2 will always be kept to support incremental compilation.')
    register('--max-subprocess-args', advanced=True, type=int, default=100, recursive=True,
             help='Used to limit the number of arguments passed to some subprocesses by breaking '
             'the command up into multiple invocations.')
    register('--lock', advanced=True, type=bool, default=True,
             help='Use a global lock to exclude other versions of pants from running during '
                  'critical operations.')

  @classmethod
  def validate_instance(cls, opts):
    """Validates an instance of global options for cases that are not prohibited via registration.

    For example: mutually exclusive options may be registered by passing a `mutually_exclusive_group`,
    but when multiple flags must be specified together, it can be necessary to specify post-parse
    checks.

    Raises pants.option.errors.OptionsError on validation failure.
    """
    if opts.loop and (not opts.v2 or opts.v1):
      raise OptionsError('The `--loop` option only works with @console_rules, and thus requires '
                         '`--v2 --no-v1` to function as expected.')
    if opts.loop and not opts.enable_pantsd:
      raise OptionsError('The `--loop` option requires `--enable-pantsd`, in order to watch files.')

    if opts.v2_ui and not opts.v2:
      raise OptionsError('The `--v2-ui` option requires `--v2` to be enabled together.')

    if opts.remote_execution and not opts.remote_execution_server:
      raise OptionsError("The `--remote-execution` option requires also setting "
                         "`--remote-execution-server` to work properly.")

    if opts.remote_execution_server and not opts.remote_store_server:
      raise OptionsError("The `--remote-execution-server` option requires also setting "
                         "`--remote-store-server`. Often these have the same value.")
