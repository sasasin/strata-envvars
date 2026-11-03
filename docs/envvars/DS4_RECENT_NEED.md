# `DS4_RECENT_NEED`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DeepSeek V4.1 エンジンの recent slot 機能で、CPU lane にいた expert を GPU の recent slot に先読み copy する条件を決めます。各層について、直近 `DS4_RECENT_WIN` 回の tick のうち何回その expert が CPU lane の対象だったら fill 候補にするかを指定します。既定値は 2 回です。recent slot 自体を有効にする設定ではありません。

## 値と判定

`env_f` は変数が未設定なら既定値を返し、設定されていれば `std::atof` で float に変換します。その結果を `int` に変換してから `std::max(1, ...)` を適用します（`src/dsv41/ds4_model.cu:1352,1577-1585`）。

| 環境変数の値 | `recent_need` |
| --- | ---: |
| 未設定 | 2 |
| `2` | 2 |
| `2.9` | 2（整数変換で小数部を切り捨て） |
| `0`、負数、空文字、数値として読めない文字列 | 1 |
| `3tail` のように数値の後ろに文字が続く値 | 数値として読めた先頭部分を整数化した値。数値部分がない場合は 1 |

全体一致の検証や無効値の警告はありません。変数は `Model::Impl` の `recent_need` 初期化時に読み取られ、そのモデルインスタンス内で保持されます。実行中に環境を書き換えても値は再読込されません（`src/dsv41/ds4_model.cu:1352,1584`）。この値に対応する CLI 引数や設定ファイルによる上書きは同ファイル内にありません。

## 有効になる条件

`recent_need` が fill 条件に使われるには、recent slot が存在する必要があります。層ごとの枠数は `o.expert_cache` が有効で、層に複数の expert slot があり、全 expert が VRAM に収まらない場合に計算されます。`DS4_RECENT` による要求枠数が正で、層が MTP 層ではなく、通常 VRAM slot と spare を残したうえで枠が確保できる場合に `l.rc_n` が正になります（`src/dsv41/ds4_model.cu:2793-2800,5553-5564`）。`DS4_RECENT` は別設定であり、未設定時の値は chunked GGUF・`ln_land` 有効・lane 環境設定が無効でない場合に 32、それ以外は 0 です。

`recent_need` が正でも、`l.rc_n == 0` なら `rc_tick` は処理を行いません。また履歴中の出現回数が閾値に届かなければ expert は選ばれません。閾値が `DS4_RECENT_WIN`（履歴長、既定 8）より大きい場合も、その履歴内では条件を満たせません。ソース上、この判定に OS 別の分岐はありません（`src/dsv41/ds4_model.cu:1584-1585,9079-9083,9114-9127`）。

## 実行時の詳細

`cache_tick` は forward の複数の経路で呼ばれ、`rc_tick` はその tick ごとに CPU lane の expert 履歴を層別に記録します。履歴は `DS4_RECENT_WIN` 件を超えると古いものから捨てられます。同一 tick 内の重複 expert は履歴に記録する前に除去されるため、閾値は tick 数として数えます（`src/dsv41/ds4_model.cu:8802-8808,9114-9119,13175-13177,13418-13420,14600-14602`）。

各 tick では直近の CPU lane 対象から最大 `DS4_RECENT_FILLS` 件（既定 2 件）を調べ、VRAM に未配置で、swap 中でなく、最近 slot に fill 中でもない expert のうち、直近履歴での出現回数が `recent_need` 以上のものを copy 候補にします。成功した copy は完了確認後に slot として採用されます（`src/dsv41/ds4_model.cu:1583-1585,9121-9155,8903-8937,9005-9011`）。

この環境変数自体について、判定値や候補選択を示すログはありません。copy に失敗すると stderr に `ds4: recent-slot fill failed, slot left unmapped: ...` を出し、その slot は公開されません。`DS4_RECENT_STATS` が設定され、tick があった場合はモデル終了時に recent slot の tick 数・平均時間・fill 数を stderr に出しますが、閾値そのものは出力しません（`src/dsv41/ds4_model.cu:1924-1928,8922-8924`）。

## 根拠

- `src/dsv41/ds4_model.cu:1352,1582-1585` — helper の変換、既定値、および下限。
- `src/dsv41/ds4_model.cu:2793-2800,5553-5564` — `DS4_RECENT` の既定値と各層の枠を作る条件。
- `src/dsv41/ds4_model.cu:8802-8808,9079-9083,9114-9155` — tick、履歴、閾値による候補選択。
- `src/dsv41/ds4_model.cu:8903-8937,9005-9011,8922-8924` — fill copy の失敗・完了と slot の採用。
- `src/dsv41/ds4_model.cu:1924-1928` — `DS4_RECENT_STATS` による終了時統計。
