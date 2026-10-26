// Runs the scripts embedded in a processed PDF inside a mock of the Acrobat
// JavaScript API. Reads a JSON job on stdin:
//   { docJs, keystroke, calcs: [{page, js}], fieldNames: [...], inputs: {page: "10000"}, keyTests: [...] }
// Prints { es5: [...errors], keys: [...], pages: {page: {juryo, dark: [cell indices]}} }.
var acorn = require("acorn");
var vm = require("vm");

var job = JSON.parse(require("fs").readFileSync(0, "utf8"));

var es5 = [];
function checkEs5(label, src) {
    try { acorn.parse(src, { ecmaVersion: 5 }); } catch (e) { es5.push(label + ": " + e.message); }
}
checkEs5("document", job.docJs);
checkEs5("keystroke", job.keystroke);
job.calcs.forEach(function (c) { checkEs5("calc page " + c.page, c.js); });

var color = {
    black: ["G", 0],
    transparent: ["T"],
    equal: function (a, b) { return JSON.stringify(a) === JSON.stringify(b); }
};
var fields = {};
job.fieldNames.forEach(function (n) {
    fields[n] = { name: n, fillColor: ["T"], value: "", get valueAsString() { return String(this.value); } };
});
var doc = { getField: function (n) { return fields.hasOwnProperty(n) ? fields[n] : null; } };
var ctx = vm.createContext({ color: color, app: { beep: function () {} } });
vm.runInContext(job.docJs, ctx);

function run(js, thisObj, event) {
    ctx.event = event;
    vm.runInContext("(function () {" + js + "\n}).call(__this)", Object.assign(ctx, { __this: thisObj }));
    return event;
}

var keys = job.keyTests.map(function (change) {
    return { change: change, accepted: run(job.keystroke, doc, { willCommit: false, change: change, rc: true }).rc };
});

var pages = {};
job.calcs.forEach(function (c) {
    fields["qty_" + c.page].value = job.inputs[c.page] || "";
    var ev = run(c.js, doc, { value: "" });
    fields["juryo_" + c.page].value = ev.value;
    var dark = [];
    for (var i = 0; i < 625; i++) {
        if (color.equal(fields["qr_" + c.page + "_" + i].fillColor, color.black)) dark.push(i);
    }
    pages[c.page] = { juryo: ev.value, dark: dark };
});

process.stdout.write(JSON.stringify({ es5: es5, keys: keys, pages: pages }));
