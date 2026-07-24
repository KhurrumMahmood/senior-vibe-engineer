/*
 * Bounded CLT Swift 6.3.3 feasibility probe for the direct sourcekitd C API.
 *
 * Compile with:
 *   clang -std=c11 -Wall -Wextra -Werror \
 *     -F /Library/Developer/CommandLineTools/usr/lib \
 *     -Wl,-rpath,/Library/Developer/CommandLineTools/usr/lib \
 *     -framework sourcekitdInProc swift-sourcekitd-direct-probe.c -o PROBE
 *
 * Pass the source, UTF-8 byte offset, and the exact compiler arguments. The
 * successful fixture request required -sdk, -target, and -resource-dir from
 * `swiftc -print-target-info`, followed by every selected-target source. Run
 * the executable beneath a 20-second subprocess timeout: the measured cold
 * wall time was 0.385358s and repeated walls were 0.061301s and 0.064745s.
 * Cursor-info resolved the normalize(_:) call to its declaration and compiler
 * USR; editor-open returned syntax-map and declaration/call substructure.
 */

#include <sourcekitdInProc/sourcekitd.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

static sourcekitd_uid_t uid(const char *value) {
  return sourcekitd_uid_get_from_cstr(value);
}

static double now_seconds(void) {
  struct timespec value;
  clock_gettime(CLOCK_MONOTONIC, &value);
  return (double)value.tv_sec + (double)value.tv_nsec / 1000000000.0;
}

static char *read_file(const char *path) {
  FILE *stream = fopen(path, "rb");
  if (stream == NULL) return NULL;
  if (fseek(stream, 0, SEEK_END) != 0) return NULL;
  long size = ftell(stream);
  if (size < 0 || fseek(stream, 0, SEEK_SET) != 0) return NULL;
  char *data = malloc((size_t)size + 1);
  if (data == NULL) return NULL;
  if (fread(data, 1, (size_t)size, stream) != (size_t)size) return NULL;
  data[size] = '\0';
  fclose(stream);
  return data;
}

static sourcekitd_object_t compiler_args(int argc, char **argv, int first) {
  sourcekitd_object_t args = sourcekitd_request_array_create(NULL, 0);
  for (int index = first; index < argc; ++index) {
    sourcekitd_request_array_set_string(args, SOURCEKITD_ARRAY_APPEND, argv[index]);
  }
  return args;
}

static int print_response(const char *label, sourcekitd_response_t response,
                          double elapsed) {
  fprintf(stderr, "%s_seconds=%.6f\n", label, elapsed);
  if (sourcekitd_response_is_error(response)) {
    fprintf(stderr, "%s_error_kind=%d\n%s_error=%s\n", label,
            sourcekitd_response_error_get_kind(response), label,
            sourcekitd_response_error_get_description(response));
    return 1;
  }
  sourcekitd_variant_t value = sourcekitd_response_get_value(response);
  char *json = sourcekitd_variant_json_description_copy(value);
  printf("{\"label\":\"%s\",\"elapsed_seconds\":%.6f,\"response\":%s}\n",
         label, elapsed, json == NULL ? "null" : json);
  free(json);
  return 0;
}

static sourcekitd_response_t send(sourcekitd_object_t request, double *elapsed) {
  double start = now_seconds();
  sourcekitd_response_t response = sourcekitd_send_request_sync(request);
  *elapsed = now_seconds() - start;
  sourcekitd_request_release(request);
  return response;
}

int main(int argc, char **argv) {
  if (argc < 4) {
    fprintf(stderr, "usage: probe SOURCE OFFSET COMPILER_ARG...\n");
    return 64;
  }
  const char *source = argv[1];
  long long offset = strtoll(argv[2], NULL, 10);
  char *text = read_file(source);
  if (text == NULL) {
    fprintf(stderr, "unable to read %s\n", source);
    return 66;
  }

  sourcekitd_initialize();

  sourcekitd_object_t open = sourcekitd_request_dictionary_create(NULL, NULL, 0);
  sourcekitd_request_dictionary_set_uid(open, uid("key.request"),
                                        uid("source.request.editor.open"));
  sourcekitd_request_dictionary_set_string(open, uid("key.name"), source);
  sourcekitd_request_dictionary_set_string(open, uid("key.sourcefile"), source);
  sourcekitd_request_dictionary_set_string(open, uid("key.sourcetext"), text);
  sourcekitd_object_t open_args = compiler_args(argc, argv, 3);
  sourcekitd_request_dictionary_set_value(open, uid("key.compilerargs"), open_args);
  sourcekitd_request_release(open_args);
  double open_elapsed = 0;
  sourcekitd_response_t open_response = send(open, &open_elapsed);
  int failed = print_response("editor_open", open_response, open_elapsed);
  sourcekitd_response_dispose(open_response);

  sourcekitd_object_t cursor = sourcekitd_request_dictionary_create(NULL, NULL, 0);
  sourcekitd_request_dictionary_set_uid(cursor, uid("key.request"),
                                        uid("source.request.cursorinfo"));
  sourcekitd_request_dictionary_set_string(cursor, uid("key.sourcefile"), source);
  sourcekitd_request_dictionary_set_int64(cursor, uid("key.offset"), offset);
  sourcekitd_object_t cursor_args = compiler_args(argc, argv, 3);
  sourcekitd_request_dictionary_set_value(cursor, uid("key.compilerargs"), cursor_args);
  sourcekitd_request_release(cursor_args);
  double cursor_elapsed = 0;
  sourcekitd_response_t cursor_response = send(cursor, &cursor_elapsed);
  failed |= print_response("cursor_info", cursor_response, cursor_elapsed);
  sourcekitd_response_dispose(cursor_response);

  sourcekitd_object_t close = sourcekitd_request_dictionary_create(NULL, NULL, 0);
  sourcekitd_request_dictionary_set_uid(close, uid("key.request"),
                                        uid("source.request.editor.close"));
  sourcekitd_request_dictionary_set_string(close, uid("key.name"), source);
  double close_elapsed = 0;
  sourcekitd_response_t close_response = send(close, &close_elapsed);
  failed |= print_response("editor_close", close_response, close_elapsed);
  sourcekitd_response_dispose(close_response);

  sourcekitd_shutdown();
  free(text);
  return failed;
}
