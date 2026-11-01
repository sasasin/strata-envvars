# `STRATA_PREFILL_LM_FORCE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。開始時の作業ツリーは `main...origin/main` で未コミット変更なし。外部ライブラリの環境変数は対象外。

## 役割

layer-major prefill がすでに選択されている場合に、短いプロンプトでもその経路を準備できるよう、最小 super-chunk 長の判定を緩めます。`STRATA_PREFILL_LM_FORCE` 単独では layer-major prefill を有効にしません。通常の1プロンプト経路では、既定の最小長を2チャンクから1にします。layer-major の計算方式そのものや通常の chunk-major 経路は、この変数では切り替えません。

実装コメントはこの変数を research 用とし、「2 chunk 未満の prompt でも layer-major walk を行う」用途を示しています。複数 prompt の `run_multi()` は別途内部フラグ `lm_force_` を立てて最小長を緩めるため、その経路でこの環境変数は必要ありません。

## 値と判定

| 環境値 | 判定 | 最小長への効果 |
|---|---|---|
| 未設定 | 無効 | `STRATA_PREFILL_LM_TOKENS` が正なら1 chunk、それ以外は2 chunks |
| 空文字 | 無効 | 未設定時と同じ |
| 先頭文字が `1`（例 `1`, `10`, `1abc`） | 有効 | 最小長を1 token相当に下げる（後続の chunk rounding は残る） |
| その他（例 `0`, `true`, ` 1`） | 無効 | 未設定時と同じ |

文字列全体の数値変換はせず、`getenv()` が非 null かつ先頭文字が `'1'` かを検査します。したがって `1` 以外の数字、空白始まり、`true` は有効にならず、`1` で始まる不正な文字列も有効です。数値範囲や負値の扱いはありません（`atoi` 等を使わないため）。値は `static const bool` に保存され、最初に `lm_force_env()` が実際に評価された後は同一プロセス内で再読込されません。`run_multi()` 中は `lm_force_` が先に真となり `||` の短絡で環境変数判定を呼ばないため、その呼び出しだけではこの cache は初期化されません。

## 有効になる条件

この変数は `Prefill::run()` が layer-major を選んだ後の `lm_prepare()` でのみ判定されます。選択自体は別の `STRATA_PREFILL_LAYER_MAJOR` と既定規則に従います。

- `STRATA_PREFILL_LAYER_MAJOR` に空でない値があれば、`atoi` が0以外となる値で layer-major を選び、0相当は選びません。明示値は既定規則や `STRATA_DEFAULTS=026` より優先します。未設定または空文字なら既定規則を使います。
- CUDA の既定は prompt path の stage 数が2以上で、かつ `STRATA_DEFAULTS=026` でない場合に ON。単一 GPU と HIP の既定は OFF。単一 GPU で使うには `STRATA_PREFILL_LAYER_MAJOR` の明示 opt-in が必要です。
- HIP build は `STRATA_LM_HIP` の先頭文字が `1` でない限り `lm_prepare()` が layer-major を拒否します。この変数が `1` でも、それ自体では HIP の拒否を解除しません。Metal build は `Prefill::run()` 冒頭の別経路から戻るため、この判定に到達しません。
- さらに、layer split の hand-off / peer GPU、画像 prompt、DFlash2 prompt taps、KVA、chunk 境界で yield する batch read、`--prefill-pipe` 計画、指定 expert format/layout、routing/row debug dump、必要バッファや VRAM/pinned RAM の不足などでは layer-major 準備が拒否されます。したがって、この変数はこれらの制約を上書きしません。
- CLI 引数にこの変数と同じ機能を直接指定する経路は見つかりません。`--prefill-pipe` はむしろ layer-major を拒否する条件です。

## 実行時の詳細

通常の `Prefill::run()` では、layer-major の値解決が真で、`lm_prepare_chain()` が成功した場合に `run_layer_major()` に進みます。各 stage の `lm_prepare()` はモデル・バッファ等の適格性を確認した後、`min_s` を計算します。`STRATA_PREFILL_LM_FORCE` が有効なら `min_s=1`、無効なら `STRATA_PREFILL_LM_TOKENS` が正のとき `m.T`（chunk 1個）、それ以外は `2*m.T`（chunk 2個）です。明示的な `STRATA_PREFILL_LM_TOKENS` は target の super-chunk 長 `want` にも使われますが、force 有効時の `min_s=1` を上書きしません。最終 super-chunk 長は chunk 単位に丸められ、prompt 長や GPU の空き容量にも制限されます。このため force は準備可能な最小 prompt 長だけを緩和し、割り当て不足などを解決するものではありません。

force が無効で短い prompt なら `lm_prepare()` は `a short prompt` で拒否し、通常経路へ戻ります。layer-major を既定で有効にしている場合、この短さだけを理由とするログは抑制されます。それ以外の拒否理由は stderr に `strata prefill: layer-major off for this prompt: ...` と出ます。準備成功時は stderr に `strata prefill: layer-major ...` として token 数、super-chunk 数と長さ、残差行の配置、VRAM 空き量などを記録します。

layer-major 経路自体では、各 layer の attention/router/shared-expert 処理を sub-chunk ごとに行い、その layer の routed experts を super-chunk 全体について実行します。ソースコメントによると routed expert の加算順と MMQ の row grouping が chunk-major と異なります。実行中の CUDA 同期・コピー等が失敗した場合、layer-major 関数はエラー文字列を返し、`Prefill::run()` は失敗を呼び出し元へ伝えます。環境変数固有の終了コードや警告は定義されていません。

## 根拠

- 環境変数の唯一の実コード読み取り、先頭文字判定と static cache: `src/prefill/prefill.cpp:5900-5903`。調査時点の `rg -n --hidden --glob '!.git/**' 'STRATA_PREFILL_LM_FORCE' .` では他の読み取り箇所はありません。`tools/par/co_bt.sh` や `tools/par/variants/*.txt` は比較実験で値を設定する記述、`tools/batch_test.py` は実験条件の説明であり、エンジン実装の別読み取り箇所ではありません。
- layer-major の値解決、既定値・明示値の優先順位、および実行/拒否ログ: `src/prefill/prefill.cpp:5894-5898,7222-7271`; `include/strata/core/sm120_series.hpp:107-120`; `include/strata/core/defaults_026.hpp:26-28`。
- backend / model / CLI 等の拒否条件と最小長、容量準備: `src/prefill/prefill.cpp:5955-6029,6031-6088`。HIP opt-in 判定は `src/prefill/prefill.cpp:5958-5968`。
- 複数 prompt の内部 force と `lm_force_` の適用、環境判定との短絡関係: `src/prefill/prefill.cpp:6188-6206,6025`。`run_multi()` は空の入力をエラーにし、準備失敗時に `prefill: multi-prompt read declined: ...` を返します。
- layer-major 実行ログおよびエラー伝播: `src/prefill/prefill.cpp:7150-7180,7254-7279`。layer-major の処理概要・加算順序: `src/prefill/prefill.cpp:5875-5892`。
