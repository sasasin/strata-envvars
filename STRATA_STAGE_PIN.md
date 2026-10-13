# `STRATA_STAGE_PIN`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリ・GPU driver 自身の環境変数動作は対象外。

## 役割

ファイルから読み込んだ expert blob を GPU cache に転送する際に使う stage buffer を、CUDA の page-locked host memory として確保するかを制御します。page-locked buffer を使うと `cudaMemcpyAsync` の転送元になり、pageable buffer で行われる driver の bounce buffer 経由のコピーを避ける狙いです。対象は `FileExpertSource` の stage buffer であり、通常の RAM arena 自体や adaptive swap 用 exchange buffer の pin 設定ではありません。

生成コマンドでは `--mmap-experts` が `FileExpertSource` を選びます。この経路は `experts.bin`、または native pack の GGUF shard をファイルから読みます。stage buffer が実際に必要なのは、GGUF の role slice、unbuffered file、または `STRATA_IO_PREFETCH` staging など、`FileExpertSource` が blob を stage pool に組み立てる経路です。モデルの expert を RAM にすべて保持してファイル tier を使わない場合、この設定の対象となる stage buffer は使われません。

## 値と判定

環境変数は `claim_stage()` が pool を増やす必要のある時に読みます。関数内 `static const int` に結果を保存するため、最初の評価後にプロセス内で値を変更しても再評価されません。

| 設定 | `pin_mode` | buffer の確保方針 |
|---|---:|---|
| unset | `-1` | `STAGE_PIN_DEFAULT` と空き RAM 条件で決める。現 HEAD の `STAGE_PIN_DEFAULT` は `0` なので pin しない |
| `atoi(value) == 0` | `0` | pin しない。例: 空文字、`0`、`true`、数字列を含まない文字列 |
| `atoi(value) != 0` | `1` | 各 stage buffer について `cudaHostAlloc` を試す。例: `1`, `1tail`, `-1` |

変換は `std::atoi` です。文字列全体の妥当性検査はなく、`atoi` は文字列先頭の空白・符号の後に続く数字列を変換し、その後の文字は判定に使いません。したがって `1tail` は有効、`0tail` は無効です。`true` は真として扱われません。空文字は 0 です。

unset 時の実装には RAM 空き量と blob サイズを確認する分岐がありますが、現 HEAD では `STAGE_PIN_DEFAULT` が `0` に固定されています。そのため現在の実効動作は、unset なら RAM 空き量にかかわらず pageable buffer です。コメントにある「空き RAM が十分なら pin」という自動方針は、この定数の現行値では有効になりません。

## 有効になる条件

- `STRATA_STAGE_PIN` が unset でなく、`atoi()` の結果が 0 以外であること。
- `FileExpertSource::claim_stage()` が新しい stage buffer を作成すること。既存 buffer の再利用では新たな確保や設定判定はありません。
- file-backed expert source の stage pool が使われること。`--mmap-experts` は `FileExpertSource` を選びますが、resident RAM の補完領域に既にある expert や stage pool を経由しない read 経路には影響しません。

設定が有効でも `cudaHostAlloc` が失敗すれば、その buffer は通常の `new[]` による pageable memory に fallback します。pageable 確保も失敗すれば `claim_stage()` は false を返します。`cudaHostAlloc` が成功するか、driver がどう処理するかは外部 CUDA runtime の動作なので、ここでは Strata 側の呼び出しと fallback のみを記します。

## 実行時の詳細

`claim_stage()` は stage pool が再利用可能な buffer を持たず、pool を拡張する場合に pin 方針を決めます。pin を試みて成功した最初の buffer では stderr に `FileExpertSource: the stage buffers are pinned (cudaHostAlloc)` を一度出します。試行が失敗した最初の buffer では `FileExpertSource: cudaHostAlloc failed for a stage buffer (%s) - pageable it is` を一度出します。pin を要求していない場合、失敗ログは出ません。

buffer は expert blob を組み立てた後、GPU cache の `fill_slot()` に渡されます。page-locked buffer の転送元は非同期 copy が終わる前に再利用しないよう、`note_async_read()` が stream 上に CUDA event を記録します。再利用時に event が未完了なら `claim_stage()` は同期を待ちます。event の作成または記録に失敗した場合は、その stream を同期します。pageable buffer では `note_async_read()` は待ち合わせを登録せず戻ります。

## 文書・測定値との照合

`docs/DETAILS.md` は `STRATA_STAGE_PIN=1` を opt-in と説明し、開発中に既定有効だった際に 0.1.41 の release gate で長い prompt 後の IQ3_S decode が壊れたため、無効のままにしたと記載しています。現 HEAD の `STAGE_PIN_DEFAULT 0` および明示値による opt-in と一致します。資料は P100 の cgroup 24 GB 条件、RTX 5070 / RTX 3060 の `--mmap-experts` 条件で測定値も報告していますが、これは資料記載の測定であり、本調査で再測定・正確性を確認したものではありません。コードコメントも IQ3_S の事象と、転送完了前に buffer が再利用される懸念を記録しています。

## 根拠

- `src/program/generate.cpp:4620-4637` — `--mmap-experts` 時に `FileExpertSource` を使うこと。
- `include/strata/core/expert_source.hpp:766-767,785-796` — staged 経路と stage buffer の役割。
- `src/core/expert_source.cpp:1233-1239,1250-1289` — 既定値、設定の読み取り・変換、pin と pageable fallback。
- `src/core/expert_source.cpp:1294-1300` — pin 成功・失敗時のログ。
- `src/core/expert_source.cpp:1363-1385,1407-1423,1467-1478,3972-3984` — buffer と cache fill、非同期 copy の同期管理。
- `docs/DETAILS.md:1689-1696` — opt-in の説明、release gate の記録、測定条件と値。
