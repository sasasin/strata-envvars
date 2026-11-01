# `STRATA_DS4_SLOT_MIN`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek-V4.1 の `strata-dsv41` エンジンが、会話状態をスロットへ退避する最小 token 数を指定します。閾値以上の会話は、別の会話に切り替えるときや serve エンジン終了時に退避候補になります。閾値未満なら `slot_put()` は何もせず、モデル状態は保存されません。

対象コードは `src/dsv41/ds4_main.cpp` の `serve()` です。CMake では専用実行ファイル `strata-dsv41` のビルドは `STRATA_BUILD_DSV41` が有効な場合に限られ、既定は OFF です。標準の `strata` ターゲットとは別の実行ファイルです（`CMakeLists.txt:906-920`）。

## 値と判定

`serve()` 内の `env_num` helper が `std::getenv()` で値を読み、設定されていれば `std::atof()` で `double` に変換します。文字列全体の検証や変換エラーの通知はありません。その結果を `std::max(1.0, value)` で下限 1 にし、`size_t` に変換して token 数と比較します（`src/dsv41/ds4_main.cpp:416-423,548-551`）。

| 環境値 | 閾値 |
|---|---:|
| unset | 1024 token |
| 空文字、数値として読めない文字列 | 1 token（`atof` が 0 を返し、下限 1 が適用される） |
| 負数、0、0 より大きく 1 未満の数 | 1 token |
| `1024`, `1024.9`, `1024tokens` | それぞれ 1024, 1024, 1024 token（小数部は `size_t` 変換時に切り捨て。数値の後ろは検査されない） |

退避判定は `t.size() < slot_min` です。したがって、実際の token 数が変換後の閾値と等しい場合も退避対象です。値の上限・範囲外の数値に対する検証や専用エラー処理はありません。

## 有効になる条件

- `--serve` 経路で `serve()` が実行される必要があります。通常の一回実行、採点・プロファイルなどの経路では、この関数内の設定を読みません（`src/dsv41/ds4_main.cpp:1388-1410`）。
- 閾値は退避機能そのものを有効化しません。`STRATA_DS4_SLOT_KEEP` が `atoi` で非ゼロとなり、かつ `STRATA_DS4_SLOT_CAP` から計算した `slot_max` が正である必要があります。直接起動時、`STRATA_DS4_SLOT_KEEP` 未設定なら slots は無効です（`src/dsv41/ds4_main.cpp:417-421,548-550`）。
- スロットディレクトリを作成・確認できない場合、エンジンは `slot_max` を 0 にして退避を無効化します。stderr に `ds4 slots: <path> is not writable - conversations are not set aside` を出します（`src/dsv41/ds4_main.cpp:647-655`）。
- 別会話への切替時は `held.empty()` の場合に現在の会話を退避します。会話の復元は画像のない prompt に限って試みます（`src/dsv41/ds4_main.cpp:801-805`）。エンジン終了時も `slot_max > 0` かつ `held.empty()` の場合に退避します（同 `:1025-1029`）。
- CLI 引数による閾値指定はありません。サーバーの `child_env()` は親環境をコピーし、設定の `env` を上書き適用してから DeepSeek-V4.1 用の既定値を設定しますが、その既定値設定は `STRATA_DS4_SLOT_KEEP`、`STRATA_DS4_SLOT_GB`、条件付きの `STRATA_DS4_SLOT_DIR` のみで、`STRATA_DS4_SLOT_MIN` は変更しません。したがって親環境の値は引き継がれ、設定の `env` に同名の値があればそちらが優先されます（`serve/server.py:3653-3667,3747-3763`）。

## 実行時の詳細

環境値はモデルのロード後、`main()` から `serve()` に入ったときに一度読みます（`src/dsv41/ds4_main.cpp:1402-1410,416-423`）。`slot_min` は関数内のローカル定数で、リクエストごとの再読込や static cache はありません。serve 中に環境を変更しても、この実行中の閾値は変わりません。サーバーがエンジンを再起動した場合は、新しい子プロセスがその起動時の環境で再評価します。

会話の退避が閾値未満で抑止されたとき、閾値専用のログや警告はありません。保存に成功すると stderr に `ds4 slots: saved a ...-token conversation...`、stdout に `NOTE sessions: saved a ...-token conversation...` が出ます（`src/dsv41/ds4_main.cpp:551-585`）。この閾値による失敗終了経路はありません。

## 根拠

- `src/dsv41/ds4_main.cpp:401-423` — スロット機能の説明、共通の `env_num` helper、既定値 1024 と型変換。
- `src/dsv41/ds4_main.cpp:547-585` — `slot_max` 条件、token 数の下限判定、保存処理と成功ログ。
- `src/dsv41/ds4_main.cpp:647-655,793-805,1025-1029` — 保存先による無効化、会話切替時・画像付き prompt の条件、終了時の退避。
- `src/dsv41/ds4_main.cpp:1388-1410` — `--serve` で `serve()` を呼び出す経路。
- `CMakeLists.txt:906-920` — DS4 専用ターゲットが opt-in であること。
- `serve/server.py:3653-3667,3747-3763` — サーバーが子プロセス環境を継承・上書きし、この変数には独自の既定値を設定しないこと。
