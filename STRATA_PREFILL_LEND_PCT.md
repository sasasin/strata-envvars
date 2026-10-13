# `STRATA_PREFILL_LEND_PCT`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--prefill auto` が prompt 用バッファを expert cache の末尾から借りる際、借りる slot 数の割合上限を指定します。生成処理の CUDA 実装と SYCL 実装で読み取ります。CUDA では layer split の自動配置・起動可能性の評価にも同じ割合を使います。固定値の `--prefill N` に対する割合上限ではありません。

## 値と判定

環境変数を `atoi` で整数に変換し、結果をそのまま割合として扱います。文字列全体の検証、範囲制限、clamp はありません。

| 値 | 結果 |
|---|---|
| 未設定 | `Prefill::pinned_share() >= 0.9` なら 90、それ以外は 85 |
| `90`, `85` など整数文字列 | その整数を割合上限として使う |
| 空文字、数値で始まらない文字列 | `atoi` の結果 0 |
| 数字の後ろに文字がある文字列 | 数字の先頭部分を変換（例: `90xyz` は 90） |
| 符号・先頭空白を含む文字列 | `atoi` の整数変換規則に従う。負数も拒否・補正されない |

このため `0` や変換結果が 0 の値では、auto の割合判定を通る正の借用枠がなくなります。100 を超える値や負数もコード上受理されますが、割合としての正規化は行いません。

根拠: `src/program/generate.cpp:3776-3780,5386-5390,6360-6364`、`sycl/src/program/generate.cpp:6007-6011`。

## 有効になる条件

- 通常の prompt 借用では、expert cache が利用でき、`--no-prefill-borrow` が指定されず、prefill chunk が有効な経路で働きます。`--prefill auto` の候補 chunk を選ぶときに、必要な cache slot 数 `k` が `k * 100 <= 上限 * cache slots` を満たすかを判定します。借用後も原則として cache に少なくとも 128 slot を残す条件があります。
- cache の slot は実際の chunk 用バッファ量から見積もります。auto は条件を満たす最大 chunk を探し、ring 用メモリ等の予算も考慮します。その結果、prompt の chunk と借用 slot 数が変わります。prompt が選択 chunk より短い場合には、その prompt に必要な量へ借用を縮めます。
- 明示的な `--prefill N` は割合判定を無効にし、指定 chunk のバッファが cache に収まるかを調べます（128 slot を残す条件は別途適用）。これは単一 cache の選択、multi-GPU layer split の評価・serve 経路の両方で確認できます。
- CUDA の layer split 自動配置では、auto chunk の cache 借用可否を全 stage について確認し、割合制限も含めて placement の起動可能性を評価します。起動時の L2 probe も同じ割合を使います。SYCL の `generate.cpp` では通常の prompt lending 箇所で読み取りますが、この変数の追加読み取りはありません。
- 借用を使わない経路、たとえば借用禁止または必要な cache/profile がなく auto が固定 chunk に切り替わる経路では、この上限は chunk 選択に作用しません。auto でも slot 条件や GPU ごとの条件を満たせなければ、より小さい chunk、借用なし、または split 不成立になります。

根拠: `src/program/generate.cpp:2464-2466,3896-3946,6396-6459,7040-7054`、`sycl/src/program/generate.cpp:6032-6049,6584-6598`。split の起動前評価は `src/program/generate.cpp:5384-5420`。

## 実行時の詳細

CUDA `src/program/generate.cpp` には読み取りが3か所あります。layer split の placement 評価用（3776行付近）、split の L2 probe 用（5386行付近）、実際の prompt lending 計画用（6360行付近）です。SYCL `sycl/src/program/generate.cpp` には prompt lending 計画の1か所があります（6007行付近）。どれも `const int64_t` の初期化時に読み、static cache ではありません。サーバー経路では、prompt lending 計画の値はその生成関数で計画が作られる際に読み込まれ、その後のリクエストごとの再読込ではありません。実行中に環境を変更しても、既に作られた計画の値は変わりません。

上限が効くと auto の scan がより大きい chunk を候補にできる場合がありますが、ring 予算や全 GPU stage の条件が先に制約することもあります。serve は `strata serve: prompt chunk auto: ...` のログで決定 chunk（CUDA は ring slot 数も）を出し、実際に借りたとき `strata serve: prompt path borrows ... cache slots` を出します。layer split で CUDA0 単独より小さい chunk になった場合は warning に cache 借用割合上限を含める経路があります。

## 文書・測定との照合

`docs/DETAILS.md:1880-1892` は `--prefill auto` の chunk 選択、streamed ring、記載条件での測定を説明していますが、`STRATA_PREFILL_LEND_PCT` の名前、既定値 85/90、または割合上限自体は記載していません。上記の変換規則と既定値はソースから確認したものです。測定値はこの環境変数の効果として転用していません。ソースのコメント（`src/program/generate.cpp:6351-6359`）には、12 GB card の Q2_0 32K prompt と pinned RAM/host copy 条件に関する tuning 値が記載されていますが、一般的な性能保証とは扱いません。

## 根拠

- `src/program/generate.cpp:3776-3780` — layer split placement 用の既定値・読み取り。
- `src/program/generate.cpp:3896-3946` — split placement の auto chunk 借用条件と起動可能性 gate。
- `src/program/generate.cpp:5384-5420` — split auto の live free figures による L2 probe。
- `src/program/generate.cpp:6351-6364,6396-6459` — 通常の prompt lending における上限と chunk/ring 選択。
- `src/program/generate.cpp:7040-7054,7140-7156` — multi-GPU prompt scan と割合上限を含む warning。
- `src/program/generate.cpp:6720-6725,6773-6779,11703-11727` — resident RAM / split lend region、auto chunk と実借用ログ。
- `sycl/src/program/generate.cpp:5998-6011,6035-6049,6584-6598,6719-6733` — SYCL の prompt lending と chunk ログ。
- `docs/DETAILS.md:1880-1892` — prompt auto chunk/ring の資料。対象変数の説明はなし。
