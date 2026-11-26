# `strata` `--resident-cpu-experts`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数。通常の `generate` 経路） |
| オプション | `--resident-cpu-experts` |
| 別名 | なし |
| 値 | 取らないフラグ |

## 役割

静的な expert profile で GPU キャッシュに入らない expert を、モデルファイルの mmap から通常 RAM にコピーして常駐させる。起動時にコピーを作り、その後は GPU キャッシュとの適応的な交換にも RAM 上のコピーを使う。RAM に収まらない場合の自動縮小・mmap 継続は `--resident-experts` と異なり、このフラグ単独では有効にならない。

## 使い方

```sh
strata --pack /path/to/model-pack --mmap-experts \
  --expert-profile /path/to/profile.bin --resident-cpu-experts
```

`--pack` で指定するモデルパックと、同じモデル用の `profile.bin` を指定する。フラグ自体には値を付けない。

## 値と既定値

- 指定すると内部フラグ `resident_cpu_experts` と `resident_cpu_explicit` を `true` にする。値の変換や数値範囲はない。指定しなければ `resident_cpu_experts` は `false`（無効）。同じフラグを複数回指定しても `true` のまま。
- 実行時には `--mmap-experts` と非空の `--expert-profile` が必須。欠けると `strata generate: --resident-cpu-experts requires --mmap-experts and a static --expert-profile` を stderr に出し、終了コード 2 で終了する。
- 通常のエンジン parser では、このフラグだけを指定しても page-lock は要求しない。`resident_pin` は既定で `false`。`STRATA_RESIDENT_PIN` の読み取りは `--resident-experts` または正の `--resident-budget-gib` の分岐にあるため、このフラグ単独の page-lock 設定には作用しない。

## 実行時の動作

profile を読み込み、GPU expert cache を初期化した後、GPU キャッシュにない expert の補集合を `FileExpertSource::pin_cache_complement` で RAM に作る。補集合は mmap ファイルを残したまま構築されるため、RAM コピーに含められなかったデータや後続の読み出しにはファイル側が使われる。`--expert-profile` の読み込みに失敗した場合はエラーを stderr に出し、終了コード 1 で終了する。

`--resident-cpu-experts` 単独では、補集合全体が RAM に入らないとコピー作成は失敗し、resident mode のエラーを stderr に出して終了コード 1 となる。`--resident-experts` を併用すると `resident_soft` も有効になり、全体が入らないときは空きメモリに収まる分（profile 上位の expert）だけを再試行する。部分コピーに成功すれば警告を出し、残りをモデルフォルダーの mmap / OS ファイルキャッシュから読む。フラグの名前が似ていても、この fallback の有無は異なる。

このコピーは GPU キャッシュ外の expert の読み出し元になる。適応的な交換が有効なら、GPU キャッシュとの交換時にファイルを再読せず RAM コピーを使う。起動時には resident RAM の量と page-locked / locked / pageable の別を stderr に表示する。prompt path が GPU cache の slot を借りる設定では、借用対象の expert も可能な範囲で RAM コピーに含める。RAM が足りず一部を含められないと、特定条件では prompt がファイルを繰り返し読む旨の警告が出る。

フラグの後に `--ssd-experts` または `--resident-budget-gib 0` を指定すると、parser が resident mode を解除する。逆に `--resident-cpu-experts` を後に置けば有効になるが、`--mmap-experts` と静的 profile の要件は残る。`--resident-experts` は `--mmap-experts`、この resident mode、page-lock 要求、headroom 設定、soft fallback をまとめて有効にする別の入口である。

## 適用条件と副作用

- ここで記述するのは CLI 索引が `engine/src/program/generate.cpp` を parser として示す通常のエンジン経路。Qwen3.6 family はモデル判定後に専用 parser へ振り分けられるため、同 parser での受理可否・動作はこの文書の対象外。
- `--layer-split` の場合は各 GPU stage の cache にある expert も補集合から除外する。`--expert-cache-remote` の helper GPU の cache にある expert も同様に扱う。少なくともソース上、この通常経路ではこれらを本フラグとの組み合わせだけで拒否していない。
- 起動時に補集合を RAM へ読み込むため、モデル規模と空き RAM に応じた大きなメモリ確保とファイル読み込みが発生する。既定の direct flag は page-lock なしである。`--resident-experts` や正の `--resident-budget-gib` と併用した場合は、それぞれの parser 分岐が pin / headroom / budget 設定も行う。
- 静的 profile に基づく GPU cache と RAM コピーの配置を使う。`--expert-profile` の内容や対応する pack の生成・検証手順はこのオプション文書では扱わない。

## 出力とエラー

- 必須の併用オプションが不足: stderr に要件を表示し、終了コード 2。
- 静的 profile の読み込み失敗: stderr に失敗理由を表示し、終了コード 1。
- resident copy の確保失敗: direct flag では `strata generate: CPU expert residency: ...` を stderr に出し、終了コード 1。soft mode を有効にした場合の再試行と fallback 警告は「実行時の動作」を参照。
- copy 成功時: `strata generate: resident RAM mode: ...` と `FileExpertSource: ... cache complement ready: ...` などの診断を stderr に出す。

## 根拠

- `engine/src/program/generate.cpp:876-887` — `resident_cpu_experts`、既定の `resident_pin` / `resident_soft`、明示指定フラグの状態。
- `engine/src/program/generate.cpp:4218-4228` — `--mmap-experts`、本フラグ、`--resident-experts` と環境変数の parser 分岐。
- `engine/src/program/generate.cpp:4236-4257` — `--ssd-experts` と `--resident-budget-gib` が resident mode を解除または有効化する条件。
- `engine/src/program/generate.cpp:4866-4878` — mmap と共有 arena の排他、および mmap / 静的 profile 要件の validation。
- `engine/src/program/generate.cpp:6746-6751` — expert profile の読み込みと失敗時の終了経路。
- `engine/src/program/generate.cpp:12077-12117` — 補集合の構築、`resident_soft` による部分再試行、警告、startup unbuffered の終了処理。
- `engine/src/program/generate.cpp:12181-12217` — 交換 buffer の確保、resident mode の診断、失敗時の警告または終了コード 1。
- `engine/src/program/generate.cpp:11908-11949` — prompt lend 領域と layer split / helper GPU の cache expert の扱い。
- `engine/include/strata/core/expert_source.hpp:774-799` — mmap を fallback として残す補集合コピー、page-lock と budget の契約。
- `engine/src/core/expert_source.cpp:3985-4003` — 補集合コピーの前提条件と初期失敗理由。
- `engine/include/strata/core/resident_ram_copy.hpp:11-23` — `STRATA_RESIDENT_PIN` の解釈。通常の `--resident-cpu-experts` 分岐からは直接呼ばれない。
- `docs/cli/000_cli_tools.md:10`、`docs/cli/README.md:1036-1042,1190-1192` — ツール ID、parser の所在、root scope と索引リンク。

調査範囲は索引が指定する `engine/src/program/generate.cpp` の parser と通常経路、および補集合コピー実装。`engine/sycl/src/program/generate.cpp` にも同じ option 文字列と別 parser が存在するが、SYCL parser 固有の挙動は本書では照合・一般化していない。
