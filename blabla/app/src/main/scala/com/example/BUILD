jvm_binary(
  name = 'bin',
  dependencies = [
    'blabla/common/library/src/main/com/example:library',
  ],
  source = 'App.scala',
  main = 'com.example.App',
  basename = 'testapp',
)


scala_js_binary(
  name = 'bin-js',
  dependencies = [
    'blabla/common/library/src/main/com/example:library-js',
  ],
  sources=globs('*.scala'),
  # main = 'com.example.App',
  # basename = 'testapp',
)