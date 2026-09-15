#!/usr/bin/env node
"use strict";

const { spawnSync } = require("node:child_process");
const path = require("node:path");

const script = path.join(__dirname, "..", "scripts", "qfpay_cli.py");
const candidates = [process.env.QFPAY_PYTHON, "python3", "python"].filter(Boolean);
for (const python of candidates) {
  const result = spawnSync(python, [script, ...process.argv.slice(2)], { stdio: "inherit" });
  if (result.error && result.error.code === "ENOENT") continue;
  if (result.error) {
    console.error(`Unable to start ${python}: ${result.error.message}`);
    process.exit(1);
  }
  process.exit(result.status ?? 1);
}
console.error("QFPay CLI requires Python 3.10+; set QFPAY_PYTHON to its executable.");
process.exit(1);
