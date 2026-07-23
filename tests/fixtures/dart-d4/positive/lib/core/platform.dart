export 'platform_stub.dart'
    if (dart.library.io) 'platform_io.dart'
    if (dart.library.html) 'platform_web.dart';

// ignore: unused_element
String _conditionalDormant() => 'not a deletion lead';
