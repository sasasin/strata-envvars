# `FNX_PF_SKIP_CONFIRM`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Flash-Next の split engine は、この変数を prefill の skip/confirm 設定として使いません。27B 向け設定名が誤って渡されたかを確認する一覧に含め、設定されていれば `Engine` の生成を拒否します。したがって、値を設定しても prefill の動作は変わりません。

## 値と判定

| 状態 | 判定と結果 |
| --- | --- |
| 未設定 | この名前については何もせず、後続の engine 初期化へ進む |
| 空文字を設定 | `std::getenv` が非 null を返すため設定ありと判定し、例外を投げる |
| 任意の非空文字列 | 値を parse せず設定ありと判定し、例外を投げる。数値・真偽値・範囲の検証や fallback はない |

値は `std::getenv(k)` の戻り値が null かどうかだけで判定されます。文字列の読み取り・変換や、この変数を無効化する CLI 引数はありません（`src/split/src/engine.cu:31-36`）。

同じループには `FNX_PF_SKIP` がこの名前より前にあります。複数の一覧内変数が設定されている場合、最初に見つかった名前で例外になるため、先行する変数も設定されているとエラー文は `FNX_PF_SKIP_CONFIRM` ではなく先行名を示します（`src/split/src/engine.cu:34-36`）。

## 有効になる条件

- `src/split/src/engine.cu` の Flash-Next `Engine` が生成される経路で検査されます。対象は `STRATA_BUILD_SPLIT` で有効化される独立した split engine です。ビルド設定上、Linux の CUDA または HIP build が対象で、CUDA/HIP とも `engine.cu` が含まれます（`CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-7,64-80`）。
- `strata-split-*` と `split_fnx_run` はいずれもこの engine source を含み、`FNX_27B=0` で build されます（`src/split/CMakeLists.txt:92-114,153-160`）。通常の Strata engine ではなく、この Flash-Next split engine の設定検査です。
- sFNX サーバーではモデルと MTP の準備後、engine を作る時点で検査されます（`src/split/tools/sfnx.cpp:1051-1062`）。`fnx_run` も Engine を生成する経路で検査されます。lab mode は `lab_check` に分岐し、そこで Engine を作る処理が対象です（`src/split/tools/fnx_run.cpp:960-988`）。
- この分岐に OS/backend、モデル状態、CLI 値、他変数による有効化条件はありません。別の一覧内変数が先に設定されている場合だけ、先述の順序でそちらのエラーが先になります。

## 実行時の詳細

検査は `Engine` コンストラクタの先頭で、各生成時に行われます。値を保存・cache しないため、後から環境が変更され、その後に別の Engine が作られれば、その時点の値が再確認されます。設定を検出すると `std::runtime_error` を投げ、コンストラクタの残りの初期化処理へ進みません（`src/split/src/engine.cu:31-36`）。

エラー文は `FNX_PF_SKIP_CONFIRM is the 27B's: Flash-Next has nothing it sets` です。sFNX は stdout の `ERR <理由>` と stderr の `sfnx: failed: <理由>` を出し、終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1030-1035,1055-1062`）。`fnx_run` は stderr に `fnx_run: <理由>` を出し、終了コード 1 を返します（`src/split/tools/fnx_run.cpp:1364-1373`）。いずれも通常の engine 起動完了ログより前の失敗です。

## 根拠

- `src/split/src/engine.cu:31-36` — コンストラクタの動的な環境変数名チェック、例外条件と文言。
- `src/split/CMakeLists.txt:64-80,92-114,153-160` — split engine の source 構成、CUDA/HIP build、`FNX_27B=0` の定義。
- `CMakeLists.txt:2945-2949` — split engine は opt-in の独立 target。
- `src/split/tools/sfnx.cpp:1030-1035,1051-1062` — sFNX の Engine 生成、エラー出力、終了。
- `src/split/tools/fnx_run.cpp:960-988,1364-1373` — `fnx_run` の Engine 生成経路と例外処理。
- `docs/envvars/000_envvers.md:582` — この名前は候補一覧にある。Strata source で確認できた意味は prefill 設定ではなく、設定時に split engine が拒否するチェックである。
