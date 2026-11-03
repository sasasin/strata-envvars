# `DS4_RECENT_STATS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek-V4.1 エンジンの終了処理で、recent slots の tick 数、tick あたり時間、expert fill の開始数・マッピング完了数、stream された expert の landing 数を stderr に集計表示します。この変数は診断出力の有無だけを変え、recent slots の割当や処理自体は有効化しません。

対象コードは `strata-dsv41` の `src/dsv41/ds4_model.cu` にあります。ビルド設定ではこの実行ファイルは `STRATA_BUILD_DSV41=ON` のときだけ追加され、既定は OFF です（`CMakeLists.txt:931-945`）。

## 値と判定

値の内容は parse されず、`std::getenv("DS4_RECENT_STATS") != nullptr` の有無だけを判定します（`src/dsv41/ds4_model.cu:1924`）。

| 環境変数の状態 | 出力条件への影響 |
| --- | --- |
| 未設定 | 統計を出さない |
| 空文字を含む任意の設定値 | 設定ありとして扱う |

`0`、`false`、数値形式などの値検証、境界値、無効値時の fallback はありません。CLI 引数や別の環境変数によるこの判定の上書きもありません。

## 有効になる条件

出力には、`DS4_RECENT_STATS` が設定されていることに加え、モデル実行中に `rc_ticks > 0` となることが必要です。統計対象は recent slots の処理に限られます。`DS4_RECENT` が 0 なら処理は止まり、レイヤーに recent slot が割り当てられていない場合も tick は記録されません（`src/dsv41/ds4_model.cu:9080-9083,1924`）。

recent slot 数 `DS4_RECENT` の初期値は 0 です。モデル初期化後、`DS4_RECENT` が未指定なら、chunked prompt、GGUF、stream lane の landing (`ln_land`)、lane を無効化する環境設定がないことを条件に 32 が既定値として使われます。それ以外は 0 です（`src/dsv41/ds4_model.cu:1577-1585,2797-2800`）。実際に slot を割り当てる際も、expert cache が有効で、layer が MTP でなく、他の VRAM slot を少なくとも 1 個残せる場合に限られます（`src/dsv41/ds4_model.cu:5553-5561`）。

## 実行時の詳細

`rc_tick()` は recent slot が存在し、対象レイヤーに slot がある場合に tick の計時を開始します。計時スコープの終了時に `rc_tick_ms` と `rc_ticks` を増やします。tick 内では CPU lane で使われた expert の履歴を更新し、直近 window の利用回数が閾値に達した expert の fill を開始します。fill の開始は `rc_fills_started`、コピー後に slot へマッピングされた fill は `rc_fills_done`、stream lane から slot に採用された landing は `rc_lands` に加算されます（`src/dsv41/ds4_model.cu:9079-9092,9110-9127,9150-9155,8972-8992,9005-9011`）。

`Model::Impl` の破棄時、recent-slot thread の終了を待った後に環境変数を読みます。設定があり、かつ tick が 1 回以上あれば、次の書式で stderr に 1 行出力します（`src/dsv41/ds4_model.cu:1915-1928`）。

```text
recent slots: <ticks> ticks, <ms/tick> ms a tick, <fills started/tick> fills started and <fills mapped/tick> mapped a tick, <streamed experts landed/tick> streamed experts landed a tick
```

各数値は対応するカウンターを `rc_ticks` で割った値で、時間は小数第 3 位、回数は小数第 2 位まで表示されます。環境変数は destructor で読み直されるため、その時点で未設定なら出力されません。ここに示されたコード内に static cache はありません。`rc_ticks == 0` の場合は、変数が設定されていても出力しません。

この変数による明示的な警告、エラー終了、値不正時の失敗経路はありません。統計出力は終了処理中の診断ログであり、実行中の出力ではありません。

## 根拠

- `CMakeLists.txt:931-945` — DSV41 engine の build option と `strata-dsv41` のソース登録。
- `src/dsv41/ds4_model.cu:1577-1602,2797-2800` — recent slots の設定、既定値、集計カウンター。
- `src/dsv41/ds4_model.cu:5553-5561,9079-9092,9110-9127,9150-9155` — slot 適用条件、tick 集計、fill 開始。
- `src/dsv41/ds4_model.cu:8972-8992,9005-9011` — landing と fill 完了の集計。
- `src/dsv41/ds4_model.cu:1915-1928` — destructor 内の環境判定と stderr 出力。

候補一覧 `docs/envvars/000_envvers.md` に名前がありますが、Strata ソースで確認できた参照は上記 destructor 内の存在チェック 1 箇所です。`docs/DETAILS.md` にはこの診断変数の追加説明は見当たりません。
