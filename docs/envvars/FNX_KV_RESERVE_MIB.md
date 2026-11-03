# `FNX_KV_RESERVE_MIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

この名前は sFNX engine が K/V pool の予約量を設定するためには使いません。Flash-Next 用 engine のコンストラクターは、この変数が環境に存在するだけで「27B 用の設定を Flash-Next に指定した」として例外にします。値の内容は読まず、予約量の計算や K/V pool の容量変更には使いません。

## 値と判定

| 環境の状態 | 判定 |
|---|---|
| 未設定 | この変数については拒否しない。engine は通常の初期化を続ける |
| 設定あり（空文字を含む） | `std::getenv(k)` が null でないため拒否する。文字列の変換・比較はしない |

同じ拒否リストには `FNX_KV_PAGES` なども含まれます。リストを先頭から検査するため、複数の対象名が設定されている場合、先に列挙された名前が例外メッセージに使われます。`FNX_KV_RESERVE_MIB` より前にある名前が未設定なら、この変数について `FNX_KV_RESERVE_MIB is the 27B's: Flash-Next has nothing it sets` を送出します。CLI 引数による上書きや fallback はありません。

## 有効になる条件

この判定は `src/split/src/engine.cu` の Flash-Next `Engine` コンストラクターにあります。CMake では sFNX の CUDA/HIP 実行ファイルと `split_fnx_run` がこの実装を使い、`FNX_27B=0` でビルドされます。CMake 上の sFNX は `STRATA_BUILD_SPLIT` の opt-in 機能で、Linux CUDA または HIP の構成に限られます。

`sfnx` はモデル等のロード後、engine の生成時に判定します。`fnx_run` では通常の実行モードで engine を作る際に判定しますが、`lab_mode(mode)` が真なら engine 生成前に lab 用経路へ戻るため、このチェックは通りません。対象コードに Windows/macOS 用 sFNX target はありません。

## 実行時の詳細

コンストラクターの冒頭で拒否リストを毎回走査し、`getenv` が非 null の項目に対して `std::runtime_error` を投げます。この名前についての値の parse や cache はありません。各 engine の生成時に環境を確認するため、同一プロセスで engine を複数回作る経路では、その都度判定されます。

`sfnx` の起動時は例外を `ERR <例外文>` と stderr の `sfnx: failed: <例外文>` に出して status 1 で終了します。`fnx_run` のトップレベルでは stderr に `fnx_run: <例外文>` を出して status 1 で終了します。拒否は engine の初期化中に起きるため、該当する実行ではその engine を使った生成処理へ進みません。

## 根拠

- `src/split/src/engine.cu:31-36` — Engine 構築時の拒否リスト、設定有無だけの判定、例外文。
- `src/split/CMakeLists.txt:1-7,64-80,92-117,153-165` — sFNX の対象環境、Engine ソースの組み込み、CUDA/HIP と `FNX_27B=0` の target 定義。
- `src/split/tools/sfnx.cpp:1051-1062` — Model/Mtp の後に Engine を生成し、生成時例外を起動失敗として扱う経路。
- `src/split/tools/sfnx.cpp:1030-1035` — `sfnx` の `ERR`、stderr、終了 status。
- `src/split/tools/fnx_run.cpp:978-989,1364-1373` — lab mode の早期分岐、通常経路での Engine 生成、およびトップレベル例外処理。
