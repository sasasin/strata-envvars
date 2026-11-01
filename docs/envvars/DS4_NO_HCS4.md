# `DS4_NO_HCS4`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査対象リポジトリの作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

Metal 版 DS4 の hyper-connection split における fallback pipeline の選択を切り替えます。該当する split 呼び出しで `hc == 4` のとき、未設定なら専用 pipeline `ds4_hc_split4`、設定済みなら汎用 `ds4_hc_split` を選びます。変数の値そのものは解釈せず、環境変数が設定されているかだけを見ます。

ただし、通常の Metal モデル実行は mix と split をまとめる `ds4_hc_mix_split` pipeline を使い、この環境変数の判定箇所を通りません。`DS4_NO_HCS4` が作用するのは、その融合処理が失敗して別々の `hc_mix` / `hc_split` 呼び出しへ進み、Metal の `hc_split` が実行される場合です。

## 値と判定

| 状態 | 判定 | `hc == 4` の Metal split pipeline |
|---|---|---|
| 未設定 | `std::getenv` が null | `ds4_hc_split4` |
| 空文字を含む任意の値が設定済み | `std::getenv` が非 null | `ds4_hc_split` |
| `hc != 4` | 値にかかわらず条件不成立 | `ds4_hc_split` |

`1`、`0`、`false`、空文字などを区別せず、空白除去・数値変換・大文字小文字判定もありません。境界値や無効値という概念はなく、設定有無だけで分岐します。CLI 引数や別の環境変数との優先順位はありません。

## 有効になる条件

- Metal 向け `strata_ds4` の実装で使われます。`metal/CMakeLists.txt` は `metal/src/engine/ds4_finish.cpp` をこの実行ファイルのソースに含めています。
- DS4 のモデル設定値が `hc == 4` である場合に限り、未設定時の専用 pipeline と設定時の汎用 pipeline の差が生じます。
- Metal の通常経路では `ds4_model.cu` が `hc_mix_split` を呼び、`ds4_finish.cpp` の fused `ds4_hc_mix_split` pipeline を実行します。この fused pipeline の選択には `DS4_NO_HCS4` を参照しません。
- fused `hc_mix_split` が `false` を返すと `src/dsv41/ds4_kernels.cu` は別々の mix と split へ fallback します。その split 呼び出しで Metal 実装が成功した場合に限り、この変数による pipeline 選択が使われます。Metal 実装も `false` を返す場合は、呼び出し側が通常の `hc_split_kernel` を起動します。
- 非 Metal build では、この環境変数を読むコード経路はありません。

## 実行時の詳細

`metal/src/engine/ds4_finish.cpp:316-345` の `hc_split()` は、Metal Context の初期化と各バッファの準備後、pipeline を取得する直前に `std::getenv("DS4_NO_HCS4")` を評価します。関数内に static cache はなく、呼び出しごとに環境を読みます。プロセス内の環境値を実行中に変更すれば、以後の `hc_split()` 呼び出しの判定に反映されます。

選択される専用 `ds4_hc_split4` は、`hc == 4` の hyper-connection split を処理する Metal kernel です（`metal/src/engine/msl/ds4_init.metal:2606-2640`）。変数設定時は同じ Metal host 関数から汎用 `ds4_hc_split` を選択します。pipeline 取得が例外を投げると `hc_split()` は `false` を返し、呼び出し側は Strata の `hc_split_kernel` に fallback します（`src/dsv41/ds4_kernels.cu:2233-2238`）。この変数専用のログ、警告、終了処理はありません。

## 根拠

- `metal/src/engine/ds4_finish.cpp:315-365` — Metal `hc_split` の入力準備、`DS4_NO_HCS4` の有無による pipeline 選択、例外時の `false`。
- `metal/src/engine/ds4_finish.cpp:369-417` — 通常の fused Metal `hc_mix_split` は `ds4_hc_mix_split` を選択し、この変数を参照しない。
- `src/dsv41/ds4_model.cu:8108-8115,8341-8348` — Metal では attention と FFN の両方が `hc_mix_split` を呼ぶ。
- `src/dsv41/ds4_kernels.cu:2233-2250` — Metal host 側の fused 処理が失敗した場合に分離処理へ進み、`hc_split` の失敗時は `hc_split_kernel` に fallback する。
- `metal/src/engine/msl/ds4_init.metal:2606-2640` — `ds4_hc_split4` kernel の実装。
- `metal/CMakeLists.txt:135-169` — DS4 ソースと Metal 実行ファイルの構成。
- `000_envvers.md:245` に候補名があります。Strata 所有ソースでの完全一致検索では、環境値を読む箇所は上記 `ds4_finish.cpp:345` のみでした。`docs/DETAILS.md` にこの変数の追加説明は見当たりません。
