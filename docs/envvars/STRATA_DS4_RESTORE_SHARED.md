# `STRATA_DS4_RESTORE_SHARED`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 サーバーが各リクエスト用に組み立てる restore point から、共有開始位置 (`shared`) を除くかを指定します。`0` のとき、サーバーは system prompt と最初の user turn の境界に対応する共有 restore point をエンジンへ送りません。user turn の開始位置 (`marks`) や末尾位置 (`tail`) はこの変数では除きません。サーバーが `strata_prefix` を有効な token 数に解決している場合も、そちらが共有位置を表すため `shared` restore point は除かれます。

## 値と判定

値全体を文字列 `"0"` と完全一致で比較します。数値変換や trim はありません。

| 値 | `shared` restore point |
|---|---|
| 未設定 | 追加可能（他の適用条件を満たす場合） |
| 空文字 | 追加可能 |
| `0` | 除外 |
| `00`、`0abc`、`false`、`1`、その他 | 追加可能 |

`STRATA_DS4_RESTORE_POINTS` が有効で restore point の計算まで進んだ後に、この変数を判定します。`STRATA_DS4_RESTORE_POINTS` はサーバー側で未設定なら 4、整数化後 0 以下なら restore point の生成を止めます（`serve/server.py:761-770,5719-5723`）。エンジン側も同名設定を初回に読み、未設定なら 4、`atoi` 後に 0 以上 `kMarksMax` 以下へ clamp して保持します（`src/dsv41/ds4_model.cu:7167-7173`）。

## 有効になる条件

サーバーの `Service.set_restore_points()` は、DeepSeek-V4.1 (`family == "deepseek41"`)、画像なし、`STRATA_DS4_RESTORE_POINTS` が有効という条件で restore point 候補を作ります。共有候補自体は、tokenizer から DeepSeek の user turn token を取得でき、最初の user turn の位置が 1024 token 以上の場合だけ作られます（`serve/server.py:773-804,5714-5725`; `RESTORE_LEAST` は同 `:758`）。

次のいずれかでは共有候補をリクエストから取り除きます。

- `STRATA_DS4_RESTORE_SHARED=0`。
- `strata_prefix` が `{"tokens": N}` の形で正の token 数に解決されている。明示 prefix だけでなく、画像のない DeepSeek-V4.1 リクエストでは `STRATA_DS4_AUTO_PIN`（既定 `1`）により system/developer 先頭メッセージが自動 prefix になる場合があります。`STRATA_DS4_AUTO_PIN=0` ならこの自動 pin は無効です（`serve/server.py:5691-5698,5733-5746`）。

prefix が空 `{}` に解決された場合は `pref.get("tokens")` が偽となるため、それだけでは共有候補を除きません。エンジンでは `shared` が渡されればその位置を使い、なければ `pin` が 256 token 以上のとき `pin` を共有位置として扱います（`src/dsv41/ds4_main.cpp:1178-1183`）。したがって、この環境変数は `pin` 自体を無効化しません。

## 実行時の詳細

対象名の参照は `serve/server.py:5727` の一箇所です。`Service.prepare()` が各リクエストの prompt を準備する際に `set_restore_points()` を呼び、その中で `os.environ.get(...)` を直接評価します。値はこの判定箇所で cache されません。プロセスの環境を実行中に変更した場合は次の評価に反映されます。

生成した候補は `req["_restore"]` に入り、サーバーは `shared=<pos>` などのキーとしてエンジンのリクエスト行へ付加します（`serve/server.py:5698,1617-1618,1630-1644`）。`STRATA_DS4_RESTORE_SHARED=0` では `shared` キーだけが省かれ、他の restore key は残ります。DeepSeek エンジンは `shared` を解析し、読み取り中に対応位置へ到達すると共有 restore point として mark します。共有 mark は既存 mark と区別されて保持管理されます（`src/dsv41/ds4_main.cpp:490-493,1178-1190`; `src/dsv41/ds4_model.cu:1263-1275,7175-7187`）。

この環境変数専用のログ、警告、エラー、終了経路はありません。観測できる差は、サーバーがエンジンへ送るリクエスト行に `shared=<pos>` が含まれるかどうかです。環境変数を読むのは Python サーバーであり、C++ エンジンがこの名前を直接読む実装は見つかりませんでした。

## 根拠

- `serve/server.py:5691-5698,5714-5730`: DeepSeek 向け候補の作成、画像・restore 設定・prefix・環境変数による除外。
- `serve/server.py:761-770,773-804`: restore point の既定値、位置の生成条件、1024 token の下限。
- `serve/server.py:5733-5746`: 自動 prefix の条件と `STRATA_DS4_AUTO_PIN` の判定。
- `serve/server.py:1617-1618,1630-1644`: 候補をエンジン向けリクエストキーへ変換。
- `src/dsv41/ds4_main.cpp:490-493,1178-1190`: `shared` / `pin` の解析と読み取り位置の計画。
- `src/dsv41/ds4_model.cu:1263-1275,7167-7187`: 共有 mark の保持と上限。
