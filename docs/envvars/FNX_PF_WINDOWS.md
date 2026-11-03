# `FNX_PF_WINDOWS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Flash-Next Engine が、27B 向けの設定を Flash-Next に誤って渡したことを検出するための拒否リストの一項目です。この変数で prefill window の数や実行動作を調整する処理はありません。`FNX_PF_WINDOWS` が設定されていると、Engine の構築を例外で中止します。`src/split/src/engine.cu:31-36`。

## 値と判定

| 状態 | 判定 | 結果 |
| --- | --- | --- |
| 未設定 | `std::getenv` が `nullptr` | この変数による拒否はしない |
| 空文字を設定 | `std::getenv` が非 null | 例外を送出 |
| 任意の非空文字列 | 値の内容は参照しない | 例外を送出 |

値の parse、空白除去、数値化、境界検査はありません。`0` も無効化値にはならず、設定されているだけで拒否されます。ほかの CLI 引数や環境変数による上書き・fallback もありません。`src/split/src/engine.cu:34-36`。

## 有効になる条件

- `FNX_PF_WINDOWS` がプロセス環境に存在し、Flash-Next の `Engine` が構築される場合に拒否されます。
- split の `strata-split-*` ターゲットは CUDA または HIP の構成でこの Engine 実装を含み、`FNX_27B=0` でビルドされます。拒否判定自体に OS、backend、GPU 世代、モデル状態による分岐はありません。`src/split/CMakeLists.txt:64-79,92-114`。
- `sfnx` はモデルと MTP の読み込み後に Engine を構築します。`fnx_run` も Engine を使うモードでは、モデルの読み込み後に構築します。したがって、設定されていても Engine を構築しない経路にはこの判定は到達しません。`src/split/tools/sfnx.cpp:1050-1061`, `src/split/tools/fnx_run.cpp:978-988`。

## 実行時の詳細

判定は各 Engine コンストラクタの冒頭で `getenv(k)` により行われます。`FNX_PF_WINDOWS` を含む7つの 27B 向け環境変数を列挙し、見つかった名前を含む `std::runtime_error` を投げます。キャッシュはなく、Engine を作るたびにその時点のプロセス環境を読みます。子プロセスへの転送や、環境変数を設定する処理はこの参照箇所にはありません。`src/split/src/engine.cu:31-36`。

拒否リストは `FNX_PF_SKIP`、`FNX_PF_SKIP_CONFIRM`、`FNX_PF_SCORE_MIB`、`FNX_PF_WINDOWS` の順に検査されます。これより前の名前も設定されている場合は、最初に一致した名前が例外メッセージに使われます。`FNX_PF_WINDOWS` が最初に一致した場合のメッセージは `FNX_PF_WINDOWS is the 27B's: Flash-Next has nothing it sets` です。`sfnx` では stderr に `sfnx: failed: ...`、標準出力に `ERR ...` を出し、終了コード 1 で終了します（Engine 構築時なので `READY` より前）。`src/split/tools/sfnx.cpp:1027-1035,1055-1062,1081-1083`。`fnx_run` では stderr に `fnx_run: ...` を出し、終了コード 1 を返します。`src/split/tools/fnx_run.cpp:1364-1373`。

## 根拠

- `src/split/src/engine.cu:31-36` — 拒否リスト、設定有無の判定、例外メッセージ。
- `src/split/CMakeLists.txt:64-79,92-114` — Engine ソースの split ターゲットへの組み込み、CUDA/HIP 分岐、`FNX_27B=0`。
- `src/split/tools/sfnx.cpp:1027-1035,1050-1062,1081-1083` — sfnx の Engine 構築、失敗出力と終了経路。
- `src/split/tools/fnx_run.cpp:978-988,1364-1373` — fnx_run の Engine 構築と例外出力・終了コード。

`docs/` 内にこの変数の動作を説明する別記述は見つかりませんでした。候補一覧 `docs/envvars/000_envvers.md` には名前がありますが、現行ソース上の役割は調整用設定ではなく、設定時に Engine を拒否するチェックです。
