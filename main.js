function xorshift32(seed) {
  seed = (seed ^ (seed << 13)) >>> 0;
  seed = (seed ^ (seed >>> 17)) >>> 0;
  seed = (seed ^ (seed << 15)) >>> 0;
  return seed >>> 0;
}

function generateSeeds(initialSeed, count) {
  const seeds = [initialSeed >>> 0];
  for (let i = 1; i < count; i++) {
    seeds.push(xorshift32(seeds[i - 1]));
  }
  return seeds;
}

function simulateNC(seeds, slotTable) {
  const results = [];

  for (let i = 0; i < 10; i++) {
    const seed1 = seeds[i * 2];     // 奇数 index（スロット）
    const seed2 = seeds[i * 2 + 1]; // 偶数 index（mod）

    const slot = seed2 % 19;
    const char = slotTable.find(item => item.id === slot);

    results.push({
      roll: i + 1,
      seed1,
      seed2,
      mod: Math.abs(seed1 % 10000),
      slot,
      name: char ? char.name : '(不明)'
    });
  }

  return results;
}
