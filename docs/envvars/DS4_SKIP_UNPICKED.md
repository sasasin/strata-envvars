# `DS4_SKIP_UNPICKED`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek V4.1 の CUDA prompt chunk 実行で、CPU lane にあり GPU へストリームする expert のうち、その chunk の routing が一度も選ばなかった expert を読み込み・コピー対象から外します。`DS4_SKIP_UNPICKED` が非ゼロなら全 chunk が対象です。これは prompt の chunk に限るストリーミング経路の制御で、常駐 VRAM expert や decode の expert 選択を変更する設定ではありません。対象名は `000_envvers.md` に候補として載っていますが、動作の根拠は以下の Strata 実装です。

## 値と判定

この変数は `std::atoi` の結果を判定します。文字列全体の厳密な数値 parse はしません。

| `DS4_SKIP_UNPICKED` | 結果 | 適用される行数しきい値 |
|---|---|---|
| 未設定 | 読み取り結果が null | `DS4_SKIP_UNPICKED_ROWS` を読む |
| `1`、`-1`、`1tail` など `atoi` が非ゼロを返す値 | 有効 | `INT_MAX`（実質すべての chunk） |
| `0`、`0tail`、空文字、変換可能な数字がない文字列 | ゼロ | `DS4_SKIP_UNPICKED_ROWS` を読む |

行数側も `atoi` で変換し、未設定なら `0`、設定時は `max(0, atoi(value))` です。したがって空文字・変換可能な数字がない文字列・`0`・負値は 0 行、`12tail` は 12 行になります。正の値 `N` では chunk の行数が `N` 以下の場合だけ対象です。`DS4_SKIP_UNPICKED` が非ゼロなら行数側より優先されます。空文字は「設定あり」だけでは有効にならず、`atoi("") == 0` として行数側へフォールスルーします。`atoi` が許す先頭空白・符号と数値後の文字列はそのまま受理されます。変換結果を検査するコードはなく、`int` で表現できない入力の扱いは実装上保証されません。

## 有効になる条件

- `src/dsv41/ds4_model.cu` の CUDA `run_dev_chunks()` が処理する chunk 経路であること。
- `Streamer` に CPU lane の streamed expert batch があること。該当する expert は `plan_streams()` が `host_list` に集めます。
- chunk が設定した行数しきい値以下であること。`DS4_SKIP_UNPICKED` が非ゼロなら通常の chunk 行数はすべてしきい値内です。
- その layer の routing bounds が確定していること。選択対象の判定は routing 後に行われます。

この設定のチェックは通常の streamed-expert 経路で行われます。`c.flow` のときは通常 batch の組み立てループが行われず、`S.b` が空なので、この skip 処理によるコピー除外は起きません。`S.b` が空の場合も効果はありません。CLI 引数による同名設定や別の優先設定はコードにありません。関連するしきい値環境変数は `DS4_SKIP_UNPICKED_ROWS` です。

## 実行時の詳細

設定値は `skip_unpicked_rows()` の関数内 `static const int` に保存されます。最初にこの関数が呼ばれた時に2変数を評価し、その後の prompt chunk 処理では再読込しません。プロセス実行中に環境を変更しても反映されません。

対象 chunk の各 layer では、routing bounds から streamed expert の virtual slot に行が割り当てられたかを調べます。割り当てのない expert はファイル読み込み前に除外され、`stream_expert()` による slot への転送も行われません。コピー処理は routing 完了を待ってから進み、選ばれた expert は従来の slot/batch 配置で処理されます。VRAM 側の expert 実行と chunk routing 自体は通常どおりです。

読み込み失敗時は処理関数が `reading layer <番号>'s experts from the model's files failed` をエラーとして返します。stream 用 slot がない場合は `no slots to stream experts into on CUDA<device番号>` で失敗します。除外またはコピーした expert があれば、終了時に stderr へ `ds4 skip unpicked: <copied> streamed experts copied, <skipped> left out (<percent>%)` を出します。全件が対象外になるなど両カウンタが 0 の場合、この行は出ません。

## 根拠

- `src/dsv41/ds4_model.cu:4423-4441` — 変数の読み取り、`atoi` 判定、行数側へのフォールスルー、static cache。
- `src/dsv41/ds4_model.cu:4426-4430,4485-4498` — chunk の skip 状態、routing layer/chunk の待機、bounds による選別。
- `src/dsv41/ds4_model.cu:4511-4524,4527-4545` — 非選択 expert のファイル読み込みとコピーの除外、読み込み失敗経路、カウンタ更新。
- `src/dsv41/ds4_model.cu:826-835` — 終了時の stderr 集計。
- `src/dsv41/ds4_model.cu:11791-11813` — layer の routing 後に bounds を登録し、コピーを進める呼び出し順。
- `src/dsv41/ds4_model.cu:12035-12111` — 通常 batch の作成、しきい値による chunk 判定、stream slot エラー、read-ahead とコピー開始。
- `src/dsv41/ds4_model.cu:12043-12080,12082-12095` — flow 経路と通常 batch 経路の分岐。
- `src/dsv41/ds4_model.cu:11826-11838` — streamed experts（CPU lane expert）の一覧と virtual slot の作成。
