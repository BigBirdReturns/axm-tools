'use strict';
(async () => {
  const parts = globalThis.__AXM_POLYBOLOS_PAYLOAD || [];
  const order = [0, 1, 3, 4, 5, 6, 2];
  const fail = message => {
    document.body.innerHTML = `<main style="font:16px system-ui;padding:2rem"><h1>AXM × Polybolos could not initialize</h1><p>${message}</p></main>`;
  };
  if (order.some(index => typeof parts[index] !== 'string')) {
    fail('The static payload is incomplete. Reload the page or open the exported standalone package.');
    return;
  }
  if (typeof DecompressionStream !== 'function') {
    fail('This browser does not provide the local gzip stream required to reconstruct the standalone surface. Use a current Chrome, Edge, Brave, or Firefox release.');
    return;
  }
  try {
    const raw = atob(order.map(index => parts[index]).join(''));
    const compressed = new Uint8Array(raw.length);
    for (let i = 0; i < raw.length; i++) compressed[i] = raw.charCodeAt(i);
    const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('gzip'));
    const html = await new Response(stream).text();
    document.open();
    document.write(html);
    document.close();
  } catch (error) {
    console.error(error);
    fail('The embedded standalone payload failed integrity-safe reconstruction.');
  }
})();
