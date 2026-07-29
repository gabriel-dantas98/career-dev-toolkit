const mode = process.argv[2];

if (mode === "hang") {
  setTimeout(() => {}, 60_000);
} else if (mode === "large") {
  process.stdout.write("x".repeat(10_000));
} else {
  process.stdout.write(
    JSON.stringify({
      args: process.argv.slice(2),
      cwd: process.cwd(),
      env: {
        PATH: process.env.PATH,
        ALLOWED_TEST_VALUE: process.env.ALLOWED_TEST_VALUE,
        SHOULD_NOT_LEAK: process.env.SHOULD_NOT_LEAK,
      },
    }),
  );
}
