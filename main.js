function xorshift32(seed) {
  seed = (seed ^ (seed << 13)) >>> 0;
  seed = (seed ^ (seed >>> 17)) >>> 0;
  seed = (seed ^ (seed << 15)) >>> 0;
  return seed >>> 0;
}

function generateSeeds(initialSeed, count) {
  const seeds = [initialSeed >>> 0];
  for (let i = 1; i < count; i++) {
    seeds[i] = xorshift32(seeds[i - 1]);
  }
  return seeds;
}

async function loadOthers() {
  const res = await fetch("others.json");
  return await res.json();
}

function simulateNC(seeds, slots) {
  const results = [];

  for (let i = 0; i < 10; i++) {
    const seed1 = seeds[i * 2];     // 1つ目の乱数
    const seed2 = seeds[i * 2 + 1]; // 2つ目の乱数

    const mod = Math.abs(seed1 % 10000);
    const slotIndex = seed2 % 19;

    const entry = slots.find(e => e.id === slotIndex);
    const name = entry ? entry.name : "(不明)";

    results.push({
      roll: i + 1,
      seed1,
      seed2,
      mod,
      slot: slotIndex,
      name
    });
  }

  return results;
}

function renderTable(results) {
  const tbody = document.getElementById("resultBody");
  tbody.innerHTML = "";

  results.forEach(r => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.roll}</td>
      <td>${r.seed1}</td>
      <td>${r.seed2}</td>
      <td>${r.mod}</td>
      <td>${r.slot}</td>
      <td>${r.name}</td>
    `;
    tbody.appendChild(tr);
  });
}

document.getElementById("simulateButton").addEventListener("click", async () => {
  const seed = parseInt(document.getElementById("seedInput").value);
  if (isNaN(seed)) return alert("シード値を入力してください");

  const others = await loadOthers();
  const slots = others.NC.slots;
  const seeds = generateSeeds(seed, 20);
  const results = simulateNC(seeds, slots);
  renderTable(results);
});
