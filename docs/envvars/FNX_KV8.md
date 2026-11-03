# `FNX_KV8`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。外部ライブラリや GPU driver の環境変数動作は対象外。

## 役割

`strata-split` の Flash-Next エンジンで、paged K/V cache の行を int8 で保存するか f16 で保存するかを選びます。未設定時は int8、`0` を指定すると f16 です。これは通常の Strata エンジンの設定ではなく、`src/split` のエンジンに限った設定です。通常エンジン側にはこの名前を読む箇所がありません。

int8 経路では K と V をそれぞれ 32 要素単位で量子化し、各グループの scale を f16 で保存します。attention の読み出し時には int8 値と scale から値を復元します。f16 経路は K/V を f16 に変換して保存します。int8 を選んだ場合は同じ f16 領域量に収まるよう K/V pool の初期ページ数を縮小します。

## 値と判定

| 環境変数の値 | 判定 | K/V cache |
|---|---|---|
| unset | 有効（既定） | int8 |
| `1` | 有効 | int8 |
| `0` | 有効 | f16 |
| 空文字、その他の文字列（例: `true`, `01`, ` 1`） | 無効値 | 例外を送出し、起動を失敗させる |

数値変換や trim は行わず、`strcmp` で文字列全体を大文字小文字を区別して比較します。設定値は `0` または `1` のちょうど一文字でなければ受理されません。無効値の例外メッセージは `FNX_KV8: 0 or 1, not '<値>'` です。既定値を変える CLI 引数や別の環境変数は、この変数の実装にはありません。

根拠: `src/split/src/kernels.cu:1874-1881`。

## 有効になる条件

- `FNX_KV8` を読むのは `src/split/src/kernels.cu` の `fnx::kv_q8()` です。`strata-split` は既定ではビルドされず、`STRATA_BUILD_SPLIT=ON` で有効にする Linux CUDA/HIP 用の別エンジンです。CMake は同じソースを CUDA または HIP としてコンパイルし、split ターゲットに `FNX_27B=0` を定義します。通常の Strata エンジン、Windows/macOS の split ビルド、split を起動しない構成にはこの読み取り経路はありません。
- Strata が split engine を子プロセスとして起動する場合、`serve/server.py:4054-4067` は現在の `os.environ` をコピーし、run config の `env` 項目があればその値で上書きします。同ファイルの `start_engine_or_fallback()` はその環境を `StrataEngine` に渡し、`serve/server.py:1152-1154` で engine プロセスを起動します。したがって継承された `FNX_KV8` は run config の `env.FNX_KV8` で上書きできます。別の CLI オプションによる上書きは確認できません。
- split engine が起動を拒否・失敗して通常の layer-split engine に fallback した場合、通常エンジンは `FNX_KV8` を読みません。split 側の int8/f16 選択が fallback 先へ引き継がれる動作はありません。

根拠: `CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-7,20-27,92-114`、`serve/server.py:4054-4067,9107-9143,1152-1154`。

## 実行時の詳細

`kv_q8()` は最初の呼び出し時に値を評価し、その真偽値を関数内の `static const bool` に保存します。通常の split エンジンでは `Engine` コンストラクターが K/V pool のページ数を計算する際に呼び出すため、エンジン初期化中に判定されます。以後の呼び出しは同じ結果を返します。`Engine` は `KvPages::q8` にこの形式を記録し、ページ／slot の配置サイズをその値で決めます。int8 のときは context 用のページ数に f16/int8 のページサイズ比を掛け、K/V の書き込みと attention 読み出しも `g.q8` で分岐します。

K/V 書き込みは各グループの最大絶対値を 127 で割った scale を求め、値を scale で割って丸めた int8 と f16 scale を保存します。f16 の場合は入力値を f16 に変換します。起動に成功すると stderr の `sfnx: loaded ... K/V pool (int8|f16) ...` 行に選ばれた形式が表示されます。

無効値の場合、`kv_q8()` は例外を送出します。`strata-split` の `main()` はモデルと MTP を読み込んだ後に `Engine` を構築するため、この値の検証はそれらのロード後です。初期化の例外は `sfnx: failed: FNX_KV8: 0 or 1, not '<値>'` を stderr に出し、`ERR FNX_KV8: 0 or 1, not '<値>'` を stdout に送って終了コード 1 で終了します。split 起動が fallback 設定を持つ場合、サーバーは失敗理由を一行で出して通常の layer split を開始します。

根拠: `src/split/src/engine.cu:31-36,70-80,371-381`; `src/split/src/kernels.cu:559-567,1670-1695,1701-1730,1874-1881`; `src/split/src/kernels.hpp:153-164`; `src/split/tools/sfnx.cpp:1050-1062,1068-1076,1027-1035`; `serve/server.py:9112-9143`。

## 根拠

完全一致検索では、変数名は `src/split/src/kernels.cu` のコメント 2 箇所と `kv_q8()` の読み取り・判定、`src/split/src/kernels.hpp` のコメントにだけ現れました。動的な名前を受け取る helper 経由での追加読み取りは見つかりませんでした。`docs/envvars/000_envvers.md` の候補一覧にも `FNX_KV8` はありますが、実装参照は上記 split engine 内に限られます。
