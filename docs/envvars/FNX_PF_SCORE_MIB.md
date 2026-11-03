# `FNX_PF_SCORE_MIB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

Flash-Next の split engine は、この名前を値として使いません。engine 構築時に環境変数が設定されているかを確認し、設定されていれば「27B 向けの設定で、Flash-Next には適用先がない」として起動を拒否します。これは通常の調整用スイッチではなく、誤ったモデル向け設定の検出です。

## 値と判定

| 環境の状態 | 判定と結果 |
|---|---|
| 未設定 | このチェックは通過する |
| 設定済み（空文字を含む） | `std::getenv` が非 null となり、`std::runtime_error` を投げる |

文字列の内容、数値変換、範囲、境界値は調べません。たとえば `0`、`1`、任意の文字列、空文字はいずれも設定済みとして同じ失敗になります。CLI 引数や他の環境変数による上書き・fallback はありません。

## 有効になる条件

この判定は `src/split/src/engine.cu` の Flash-Next `fnx::Engine` コンストラクターにあります。split engine は opt-in の `STRATA_BUILD_SPLIT` で組み込まれる独立実行系で、CMake の条件上 Linux CUDA または HIP のビルドが対象です。通常の Strata engine 全般に適用されるチェックではありません（`CMakeLists.txt:2947-2949`, `src/split/CMakeLists.txt:1-5,64-80`）。

## 実行時の詳細

`Engine` のコンストラクターは候補名を並べたループでそれぞれ `std::getenv(k)` を呼びます。`FNX_PF_SCORE_MIB` が設定済みなら、値を保持・変換せず、例外メッセージ `FNX_PF_SCORE_MIB is the 27B's: Flash-Next has nothing it sets` を生成します。読み取りはコンストラクターごとに行われ、static cache はありません。

`sfnx` のサーバー起動経路では GGUF モデルと MTP を用意した後に `Engine` を構築します。例外は `fail()` に渡り、stdout に `ERR ` 接頭辞付きの行、stderr に `sfnx: failed: ` 接頭辞付きの行を出し、終了コード 1 でプロセスを終了します。そのため設定がある場合、モデル/MTP の準備後、サーバー開始前に停止します（`src/split/tools/sfnx.cpp:1051-1062,1030-1035`; stdout 出力は `:58-62`）。

## 根拠

- `src/split/src/engine.cu:31-36` — 候補名の列挙、設定有無の読み取り、例外文言。
- `CMakeLists.txt:2947-2949`, `src/split/CMakeLists.txt:1-5,64-80` — split engine の opt-in と build/backend 条件、および `engine.cu` を含む実行系。
- `src/split/tools/sfnx.cpp:1051-1062,1030-1035,58-62` — engine 構築時点と失敗時の stdout/stderr・終了処理。
