// Prints qrV2M matrices as JSON: node qr_dump.js <text> [mask]
var fs = require("fs"), vm = require("vm"), path = require("path");
var ctx = {};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../js/qr_v2m.js"), "utf8"), ctx);
var text = process.argv[2];
var mask = process.argv[3] === undefined ? undefined : Number(process.argv[3]);
var m = ctx.qrV2M(text, mask);
process.stdout.write(JSON.stringify(m === null ? null : m.map(function (r) { return r.map(Number); })));
