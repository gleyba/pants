java_library(
  name='common-math3',
  dependencies = [
    'blabla/3rdparty/jvm',
  ],
)

scala_library(
  name = 'library',
  dependencies = [
    ':common-math3'
  ],
  sources=globs('*.scala'),
)

scala_js_library(
  name = 'library-js',
  dependencies = [
    ':common-math3'
  ],
  sources=globs('*.scala'),
)