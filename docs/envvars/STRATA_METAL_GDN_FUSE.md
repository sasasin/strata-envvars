# `STRATA_METAL_GDN_FUSE`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありませんでした。候補一覧 `docs/envvars/000_envvers.md` に記載されている名前です。

## 役割

Metal の prompt chain が GDN 層の4入力射影（`attn_qkv`、`attn_gate`、`ssm_alpha`、`ssm_beta`）を一つの連結 GEMM として処理する経路を、`STRATA_METAL_GDN_FUSE=0` で無効にします。無効時は各射影を個別に dequantize し、4回の GEMM を実行します。この切替は prompt chain の GDN 入力射影に対するもので、GDN scan や decode 側の別処理を選ぶものではありません。

## 値と判定

`getenv()` の結果を文字列全体で `"0"` と比較します。数値変換や trim、大文字小文字変換はありません。

| 環境値 | `off` | fused 経路の選択（Apple M5 系の場合） |
|---|---:|---|
| 未設定 | false | 有効 |
| 空文字 | false | 有効 |
| 文字列がちょうど `0` | true | 無効 |
| その他すべて（例: `1`, `00`, `0 `, `false`） | false | 有効 |

値が `0` 以外でも、後述の Apple M5 系という条件を満たさなければ fused 経路にはなりません。CLI 引数や別の環境変数による上書きは、この選択関数では確認できません。

## 有効になる条件

- Metal backend の `Window` が prompt を処理し、prompt chain の `pc_setup()` が呼ばれること。
- 通常の Metal prompt routing で、`STRATA_METAL_PROMPT=window` が選ばれておらず、streaming でなく、prompt 長が `STRATA_METAL_PROMPT_MIN` 以上であること。後者の既定値は 32 です。条件を満たさない prompt は別経路へ進むため、この変数は適用されません。
- `gdn_fused_inputs()` に渡されたデバイス名が `"Apple M5"` で始まること。M5 系以外では環境値にかかわらず false です。
- 上記に加えて、`STRATA_METAL_GDN_FUSE` が未設定、空文字、または文字列 `"0"` 以外であること。

この変数による選択に CLI の別スイッチはありません。値が何であっても Metal prompt chain が使われない実行では効果はありません。

prompt の routing 条件は `metal/src/engine/window.cpp:3047-3077` にあります。streaming prompt は別の prompt GEMM / decode-window 経路へ進み、`STRATA_METAL_PROMPT=window` も decode-window 経路を選択します。

## 実行時の詳細

`gdn_fused_inputs()` 内の関数ローカル `static const bool off` は、最初に関数が呼ばれたときに環境を読み、その後はプロセス内で値を保持します。環境変数は起動後に変更しても再評価されません。`Window::pc_setup()` は prompt buffer を初期化・拡張するときにこの関数を呼び、結果を `PromptBufs::fused` に保存します。すでに確保済みの buffer で要求サイズが収まる場合は setup を早期終了するため、選択を再計算しません。

`fused` が true の場合、4つの重みを `Wcat` の連結領域に dequantize し、`gemm(..., 16480, N)` を1回実行します。その結果を stride 16480 の `gdn_pre` と `gdn_post` に渡します。false の場合は4つの重みを個別 buffer に dequantize して、出力サイズ 10240、6144、48、48 の GEMM をそれぞれ実行し、通常 stride の `gdn_pre` / `gdn_post` を使います。

この環境変数専用のログ、警告、エラー出力は見つかりませんでした。setup 時には一般的な `strata metal: prompt kernels ... ready ...` ログが出ます。`STRATA_METAL_TRACE` または `STRATA_METAL_PROFILE` が設定されている場合は prompt の計測ログも出ますが、いずれも fused 選択を表示しません。ソースコメントはこの連結 GEMM が個別 GEMM と bit-identical と記していますが、ここではその実測・正確性を独立検証していません。

## 根拠

- `metal/src/engine/window.cpp:81-87` — 変数の読み取り、文字列 `"0"` との完全一致判定、Apple M5 系のデバイス条件。
- `metal/src/engine/window.cpp:141` — `PromptBufs` に fused 選択を保持するフィールド。
- `metal/src/engine/prompt_chain.inc:49-60,71-79,92-98` — prompt buffer setup と fused / 個別用バッファの確保。
- `metal/src/engine/prompt_chain.inc:204-252` — prompt の GDN 層での重み dequantize、GEMM 回数、`gdn_pre` / `gdn_post` 呼び分け。
- `metal/src/engine/prompt_chain.inc:435-461` — prompt chain の呼び出し、buffer setup、chunk 処理、関連する一般ログ。
- `metal/src/engine/window.cpp:3045-3077` — この prompt chain が選ばれる長さ・streaming・`STRATA_METAL_PROMPT` 条件。
- `docs/envvars/000_envvers.md:1035` — 候補一覧への掲載。
