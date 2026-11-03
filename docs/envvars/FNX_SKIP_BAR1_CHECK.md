# `FNX_SKIP_BAR1_CHECK`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

sFNX のモデル読み込み時に、各カードの BAR1 サイズがそのカードの全 VRAM を覆うかを調べる検査を省略するフラグです。変数を読むのは `src/split/src/model.cpp` の `check_cards()` だけです。現在の CMake 定義では CUDA/HIP とも `FNX_HOSTRING=1` でビルドされ、この構成では BAR1 検査がもともと実行されません。そのため、現在の CMake 対象では有効値にしても検査動作は変わらず、stderr の通知だけが出ます。

## 値と判定

`env_flag()` は `env_int(name, 0) != 0` です。未設定は `0`（無効）。設定値は整数として文字列全体を parse し、ゼロなら無効、ゼロ以外なら有効です。既定値への fallback は未設定の場合だけで、設定済みの無効な文字列はエラーになります。

| 環境変数の値 | 判定 |
| --- | --- |
| 未設定 | `0`。無効、通知なし |
| `0`、`+0`、`-0` など、parse 結果が 0 | 無効、通知なし |
| `1`、`-1`、`+2` など、parse 結果が 0 以外 | 有効。`fnx: FNX_SKIP_BAR1_CHECK=1: the cards' BAR1 is not checked against their memory` を stderr に出す |
| 空文字、`true`、`1x`、前後の空白を含む値、`long long` の範囲外 | 整数全体の parse に失敗し、例外になる。値の部分 parse や trim はしない |

parse は任意の符号と 10 進数字を `strtoll` で読み、末尾が文字列終端であること、および `ERANGE` でないことを確認します。整数としての別の範囲制限や clamp はありません（`src/split/src/env.hpp:15-22,33-40,51-52`）。

## 有効になる条件

- sFNX の `Model` を構築して `check_cards()` に到達したときに読み取られます。モデルの GGUF メンバー初期化と、可視カード数がビルド時の `NCARD` と一致する確認の後です。設定ファイルや CLI 引数による上書きはありません（`src/split/src/model.cpp:100-105,1253-1265`）。
- 現行 CMake の `strata-split-*` は CUDA、HIP とも `FNX_HOSTRING=1` を定義し、`split_fnx_run` も同じ値を定義します（`src/split/CMakeLists.txt:96-114,153-160`）。このビルドでは `check_cards()` が `skip_bar1` を読みますが、`FNX_HOSTRING` 分岐は値を使用せず、BAR1 検査と identity IOMMU 検査の両方を行いません（`src/split/src/model.cpp:121-127`）。有効値でも実行時の検査省略効果はありません。
- `FNX_HOSTRING=0` のビルドでは、カードごとのアーキテクチャ確認と identity IOMMU 確認は変数の値にかかわらず行い、`FNX_SKIP_BAR1_CHECK` がゼロの場合に限って BAR1 を確認します（`src/split/src/model.cpp:103-127`）。調査対象 commit の CMake にはこの設定で作る sFNX 実行ターゲットはありません。

## 実行時の詳細

`check_cards()` ごとに環境を読み直し、値を static cache しません。sFNX サーバーでは起動時の `m.emplace(...)` がモデルを構築し、その前に CLI 引数と別の環境チェックを行います（`src/split/tools/sfnx.cpp:1040-1061`）。sFNX のモデル読み込み例外は `ERR ...` を stdout、`sfnx: failed: ...` を stderr に出して終了コード 1 で終了します（同 `:1027-1035`）。したがって空文字や不正値はモデル構築中に失敗します。診断用 `split_fnx_run` もモデル構築時に読み、例外を `fnx_run: ...` として stderr に出し、終了コード 1 を返します（`src/split/tools/fnx_run.cpp:1364-1373`）。

`FNX_HOSTRING=0` で BAR1 検査が有効な場合、BAR1 が VRAM より小さいと `require_bar1_covers()` が例外を出します。メッセージには BAR1/VRAM の MiB 値と `FNX_SKIP_BAR1_CHECK=1` の案内が含まれます。sysfs の BAR1 情報が開けない、読めない、または不正な場合も例外です（`src/split/src/model.cpp:79-90`; `src/split/src/card_check.hpp:60-79,102-110`）。変数でこの検査を省略しても、カードのアーキテクチャ確認は残ります。現行の `FNX_HOSTRING=1` ではこの BAR1 検査エラー経路に入りません。

完全一致の参照は、読み取りと通知の `src/split/src/model.cpp:101-102`、BAR1 不足時の案内 `src/split/src/card_check.hpp:110`、およびそのメッセージを確認するテスト `src/split/tools/card_check_test.cpp:90-99` です。環境からの読み取りは `env_flag()` 経由の `model.cpp` の一箇所で、テスト参照は本番の読み取り根拠にはしていません。`docs/DETAILS.md` にこの変数の追加説明は見つかりませんでした。

## 根拠

- `src/split/src/env.hpp:15-22,33-40,51-52` — 整数全体の parse、未設定の既定値 0、非ゼロ判定。
- `src/split/src/model.cpp:100-127,1253-1265` — 読み取り・通知、ビルド macro による BAR1 検査分岐、モデル構築時期。
- `src/split/src/card_check.hpp:60-79,102-110` — BAR1 の読み取り・サイズ条件・例外文。
- `src/split/CMakeLists.txt:96-114,153-160` — CUDA/HIP 実行ターゲットと診断ターゲットの `FNX_HOSTRING=1` 定義。
- `src/split/tools/sfnx.cpp:58-63,1027-1035,1040-1061`、`src/split/tools/fnx_run.cpp:1364-1373` — 例外の観測方法と stdout 出力。
