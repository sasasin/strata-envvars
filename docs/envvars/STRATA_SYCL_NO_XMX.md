# `STRATA_SYCL_NO_XMX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-24` 時点）。

## 役割

Inkling 2 Mini の SYCL backend で、oneMKL XMX GEMM dispatch を抑止するスイッチです。`1` で無効化すると、線形層と MoE の XMX 関数が不採用を返し、呼び出し側は SYCL SG16 の通常カーネルへ進みます。oneMKL が組み込まれていない build では XMX dispatch 自体がコンパイルされず、同じ通常カーネル経路です（`engine/src/inkling2/sycl/ink_sy_xmx.h:23-29,418-420,517-520`; fallback は `engine/src/inkling2/sycl/ink_sy_runner.h:394-420` と `engine/src/inkling2/sycl/ink_sy_vision.h:145-149`）。

この値は SYCL エンジンの演算経路に関わり、CLI 引数としては解析されません。対象の直接参照は `engine/src/inkling2/sycl/ink_sy_common.h:50` の `std::getenv` です。索引の名前が現れる箇所のうち、`docs/SETTINGS.md`、`docs/INTEL.md`、`terminal/data/settings-register.json` は資料・設定レジストリ、`ink_sy_xmx.h:6` と `ink_sy_common.h:46-47` はコメントであり、追加の読み取りではありません。`engine/src/inkling2/sycl/ink_sy_common.h:304-305` は同じ共通関数の呼び出しです。

## 値と判定

`sy_no_xmx_requested()` は初回に `STRATA_SYCL_NO_XMX` を読みます。値が未設定または空文字なら旧名 `INK_SYCL_NO_XMX` を読み、最終的に選ばれた文字列の先頭文字が `'1'` の場合だけ `true` です。文字列全体の比較や数値変換はせず、大文字小文字・空白の正規化もありません（`engine/src/inkling2/sycl/ink_sy_common.h:48-55`）。

| build / 値 | 判定 |
|---|---|
| すべて: `STRATA_SYCL_NO_XMX` 未設定または空文字 | `INK_SYCL_NO_XMX` にフォールバック。旧名も未設定・空なら無効化要求なし |
| すべて: 選ばれた値が `1`、`10`、`1anything` | 先頭が `1` なので無効化要求あり |
| すべて: 選ばれた値が `0`、`true`、`false`、`on`、` 1`、`anything`、空文字 | 先頭が `1` でないので無効化要求なし。ただし新名が `0` など非空なら旧名にはフォールバックしない |
| `INK_SYCL_USE_ONEMKL` build | 要求なしなら XMX dispatch を利用可能。要求ありなら XMX 関数が不採用を返す |
| `INK_SYCL_USE_ONEMKL` なし | XMX 関数は常に不採用を返す stub。変数で既存の XMX 経路をさらに切り替えることはない |

## 有効になる条件

- XMX を無効化する効果があるのは、Inkling SYCL backend の実行経路です。ほかの backend や別の SYCL runner にこの名前の読み取りは見つかりません（`engine/src/inkling2/sycl/ink_sy_common.h:48-55`; `engine/src/inkling2/sycl/CMakeLists.txt:7-9,28-40`）。
- XMX を使う経路が存在するには、configure 時に oneMKL の BLAS header が見つかって `INK_SYCL_USE_ONEMKL` が定義されている必要があります。ない場合、XMX entrypoint は stub です（`engine/src/inkling2/sycl/CMakeLists.txt:28-40`; `engine/src/inkling2/sycl/ink_sy_xmx.h:14-16,23-29,517-520`）。
- 有効な無効化要求でも、通常カーネルへの移行には各呼び出し側の処理が必要です。linear BF16/Q8ROW/S-format は XMX entrypoint の不採用後に SG16 kernel を呼び、Vision BF16 も同様です（`engine/src/inkling2/sycl/ink_sy_runner.h:394-420`; `engine/src/inkling2/sycl/ink_sy_vision.h:145-149`）。
- MoE XMX dispatch は XMX が有効な場合にも対象数で制限されます。通常の非 hybrid runner では `M >= 32` の分岐で候補を集め、expert ごとの routed row 数が閾値以上のものを XMX に渡します（`engine/src/inkling2/sycl/ink_sy_runner.h:772-794`）。hybrid runner では VRAM 内 expert の row 数を閾値と比較し、cold expert は XMX entrypoint が不採用なら SG16 経路へ進みます（`engine/src/inkling2/sycl/ink_sy_hybrid.h:774-799,801-815,839-840`）。
- 閾値は別変数 `INK_SYCL_XMX_MOE_MIN_N` が非空なら `atoi` で読み、最低 1 に clamp します。未設定または空文字なら 12 です。この閾値は `STRATA_SYCL_NO_XMX` の優先順位を変えません（`engine/src/inkling2/sycl/ink_sy_xmx.h:31-37,487-491`）。
- `dev_caps()` の初期化ではこの要求が true だと `has_xmx_sg16` を立てませんが、リポジトリ内でこのフィールドを読む箇所は見つかりませんでした。XMX dispatch の可否は別途 `xmx_enabled()` が判定します（`engine/src/inkling2/sycl/ink_sy_common.h:290-318`; `engine/src/inkling2/sycl/ink_sy_xmx.h:23-29`）。

## 実行時の詳細

`sy_no_xmx_requested()` の関数内 `static const bool` に値を保存するため、環境変数はプロセス内でこの関数が最初に呼ばれた時点で評価され、それ以降の変更は反映されません。`dev_caps()` も関数内 static で初期化時に同じ判定を利用します（`engine/src/inkling2/sycl/ink_sy_common.h:48-55,290-305`）。

oneMKL build で要求が有効な場合、XMX entrypoint は開始時に `false` を返すため、XMX scratch 確保や GEMM 呼び出しには進みません。linear dispatch は形式別の SG16 kernel へ移り、MoE は SG16 expert kernel 側へ振り分けられます（`engine/src/inkling2/sycl/ink_sy_xmx.h:419-420,441-442,464-465,487-491`; `engine/src/inkling2/sycl/ink_sy_runner.h:394-420,772-803`; `engine/src/inkling2/sycl/ink_sy_hybrid.h:778-799,813-815`）。この変数を判定する CLI、サーバーモード、モデル状態別の分岐はありません。実際の影響は上述の SYCL dispatch が実行されたときに限られます。

## ログと測定値

このスイッチの値判定や XMX 不採用を通知するログ出力は、確認した読み取り・dispatch 箇所にはありません。値が `1` 以外でも無効値エラーにはならず、無効化要求なしとして処理されます。XMX entrypoint の `false` は呼び出し側の通常 SG16 経路選択に使われます（`engine/src/inkling2/sycl/ink_sy_common.h:48-55`; `engine/src/inkling2/sycl/ink_sy_xmx.h:419-420,517-520`; `engine/src/inkling2/sycl/ink_sy_runner.h:394-420`）。

Strata の `docs/INTEL.md:316-331` は、Alchemist の Inkling 2 Mini で同じ prompt を再実行したときの回答の再現性と、XMX 無効時の prompt 速度を報告しています。記載条件は A750、Inkling-2-Mini UD-IQ1_S、4 回の交互実行、spread 0.1 で、prompt は 45 から 17 tok/s、decode は 2.1 tok/s のままです。これは資料中の報告値であり、本調査では再測定していません。資料の別節 `docs/INTEL.md:448` は prompt 読み取りを「約 60%」と要約しています。ソースコードは XMX 経路を切り替える事実を示しますが、性能値や出力の再現性を保証する条件・挙動は規定していません。

## 根拠

- 読み取り、旧名への fallback、値判定、static cache: `engine/src/inkling2/sycl/ink_sy_common.h:46-55`
- device capability cache と XMX capability flag: `engine/src/inkling2/sycl/ink_sy_common.h:290-318`
- oneMKL の任意 build 条件: `engine/src/inkling2/sycl/CMakeLists.txt:28-40`
- XMX 有効判定と各 XMX entrypoint の guard / stub: `engine/src/inkling2/sycl/ink_sy_xmx.h:23-29,31-37,418-520`
- 線形層と Vision の fallback: `engine/src/inkling2/sycl/ink_sy_runner.h:394-420`; `engine/src/inkling2/sycl/ink_sy_vision.h:145-149`
- MoE 経路と threshold: `engine/src/inkling2/sycl/ink_sy_runner.h:772-803`; `engine/src/inkling2/sycl/ink_sy_hybrid.h:774-815,839-840`
- Strata の測定報告: `docs/INTEL.md:316-331,448`
