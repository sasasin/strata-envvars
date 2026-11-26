# `STRATA_METAL_STUBS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

Metal エンジンで Metal 実装がまだない kernel entry point の stub に到達したとき、通常の終了動作を診断用のログ出力と return に切り替える。既定動作は entry point 名を stderr に出してプロセスを終了する。`log` は経路確認用であり、stub に実装を与えたり出力を書き込んだりする設定ではない（`engine/metal/src/engine/missing.cpp:1-5,14-28`）。

## 値と判定

`missing()` の関数内 `static` 初期化で `std::getenv` を一度呼び、取得した文字列全体を大小文字を区別して `"log"` と比較する。数値変換、trim、部分一致はしない。空文字は設定済みでも `log` ではないため既定動作になる。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| Metal エンジンの stub 到達時 | `log_only=false`。stderr に不足 entry point を出し、終了コード 86 で終了 | 完全一致の `log`（例: `log`） | 空文字、`1`、`0`、`LOG`、`log `、`xlog` など。いずれも警告や fallback ではなく既定の終了動作 |

比較は `std::string(v) == "log"` なので、値全体が一致する必要がある（`engine/metal/src/engine/missing.cpp:14-18`）。

## 有効になる条件

- Apple/macOS 向け Metal ビルドのエンジンで、未実装 entry point の stub が実際に呼ばれること。Metal CMake は Apple 以外では構成を失敗させ、`METAL_CPP_DIR` が無い場合はデバイスランタイムとエンジンを作らず、`STRATA_METAL_ENGINE=OFF` の場合もエンジンを作らない。エンジンのソース glob には `missing.cpp` と `stubs*.cpp` が含まれる（`engine/metal/CMakeLists.txt:18-20,82-109,150-177`）。
- 値が `log` でも、stub に到達しなければ何も起きない。CLI、サーバーモード、モデル状態などをこの変数自身が判定する処理はない。どの経路が stub に到達するかは呼び出される entry point に依存する（`engine/metal/src/engine/missing.cpp:14-18`）。
- 他の環境変数や CLI 引数によるこの値の上書きは、対象名の全参照では見つからない。Strata 側で子プロセスへ転送・上書きする処理も見つからない。

## 実行時の詳細

`strata::metal_engine::missing(const char*)` が初めて呼ばれたときに値を読み、`static const bool log_only` に保存する。したがってプロセス起動後に環境を変更しても、そのプロセス内では再評価されない。`log` 以外なら `strata metal: <entry point> has no Metal implementation yet` を stderr に出し、stderr を flush して `_Exit(86)` する。

`log` の場合は mutex で保護したプロセス内の set に entry point 名を追加し、新しい名前に限って `strata metal: STUB <entry point>` を stderr に出して関数から戻る。同じ名前の再呼び出しでは追加ログを出さない。`missing()` 自体は出力引数を書き換えないが、呼び出し元 stub が `return {}` 等を実行する場合はその戻り値を返す。未実装処理を実行した結果が必要な実行には使えない（`engine/metal/src/engine/missing.cpp:14-28`。stub の呼び出し例: `engine/metal/src/engine/stubs_0219.cpp:34-50`）。

## ログと測定値

終了する経路では stderr に `strata metal: <name> has no Metal implementation yet` を出して flush した後、終了コード 86 で終了する。`log` 経路では未出現の名前ごとに stderr へ `strata metal: STUB <name>` を出し、終了・flush の処理は行わない（`engine/metal/src/engine/missing.cpp:19-28`）。stdout への出力や測定値はない。

## 根拠

- 値の読み取り、判定、cache、終了・ログ: `engine/metal/src/engine/missing.cpp:14-28`
- Metal ビルド条件と stub 群の取り込み: `engine/metal/CMakeLists.txt:18-20,82-109,150-177`
- stub から `missing()` を呼ぶ例: `engine/metal/src/engine/stubs_0219.cpp:34-50`
