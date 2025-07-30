// Xorshift32
function xorshift32(seed) {
  seed ^= (seed << 13) >>> 0;
  seed ^= (seed >>> 17) >>> 0;
  seed ^= (seed << 15) >>> 0;
  return seed >>> 0;
}

// シード列を作成
function generateSeeds(initialSeed, count) {
  let seeds = [initialSeed >>> 0];
  for (let i = 1; i < count; i++) {
    seeds[i] = xorshift32(seeds[i-1]);
  }
  return seeds;
}

// others.json をロード
async function loadOthers() {
  const res = await fetch('others.json');
  return res.json();
}

// NCガチャ結果を生成（レア被りなし）
function simulateNC(seeds, others) {
  const results = [];
  const slots = others.NC.slots;
  const thresholds = others.NC.rarityThresholds;

  for (let i = 0; i < 10; i++) {
    const s1 = seeds[i * 2];     // スロット決定用
    const s2 = seeds[i * 2 + 1]; // レアリティ判定用

    const slotIndex = s1 % slots.length;
    const rarityRand = Math.abs(s2 % 10000);

    let rarity = 'ノーマル';
    if (rarityRand >= thresholds.normal && rarityRand < thresholds.rare) rarity = 'レア';
    if (rarityRand >= thresholds.rare) rarity = '激レア';

    results.push({
      roll: i + 1,
      slot: slots[slotIndex].id,
      name: slots[slotIndex].name,
      rarity
    });
  }
  return results;
}

// 結果を表示
function displayResults(results) {
  const tbody = document.querySelector('#results tbody');
  tbody.innerHTML = '';
  results.forEach(r => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.roll}</td>
      <td>${r.slot}</td>
      <td>${r.name}</td>
      <td>${r.rarity}</td>
    `;
    tbody.appendChild(tr);
  });
}

// イベント処理
document.getElementById('drawButton').addEventListener('click', async () => {
  const seed = parseInt(document.getElementById('seedInput').value);
  const others = await loadOthers();
  const seeds = generateSeeds(seed, 20); // 10連×2シードずつ
  const results = simulateNC(seeds, others);
  displayResults(results);
});
