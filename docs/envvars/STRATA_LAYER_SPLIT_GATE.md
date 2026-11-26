# `STRATA_LAYER_SPLIT_GATE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

この変数は、自動レイヤー分割の探索中に startability gate の計算値を stderr に出す診断スイッチです。設定しても gate の判定条件や選ばれる分割は変わりません。`can_start` 内で、候補の分割位置、選ばれた prompt chunk、各 stage の cache 使用量・容量・残量・必要量・推定 slot 数を表示します（`engine/src/program/generate.cpp:7174-7189,7205-7217`）。

探索対象は `--serve` で有効な複数 GPU の `--layer-split auto` です。探索本体は `multi_gpu && split_auto` のときに実行されます（`engine/src/program/generate.cpp:4803-4805,6959-6961`）。この変数は設定名に「GATE」を含みますが、startability gate を切り替える設定ではありません。実際の gate は `gate_on` で管理され、環境変数とは独立しています（`engine/src/program/generate.cpp:7246-7247,7266-7269`）。

## 値と判定

`std::getenv(...) != nullptr` だけで設定有無を判定します。文字列の内容は読まず、空文字も設定ありです。値の変換、数値範囲、空白、大文字小文字の検査はありません（`engine/src/program/generate.cpp:7206`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| `can_start` が呼ばれる自動分割探索 | 診断行を出さない | 空文字、`0`、`1`、`false`、その他任意の文字列で診断行を出す | 該当なし。未設定だけが無効 |

## 有効になる条件

- `--layer-split auto` が `--serve` とともに有効で、複数 GPU を使う自動分割探索に到達する必要があります。`--layer-split auto` でも可視 GPU が一つなら split を解除して探索しません（`engine/src/program/generate.cpp:4803-4807,4836-4839`）。
- 候補が探索の現 best より良い評価を持ち、startability を調べる経路に進むと `can_start` が呼ばれます。2 段・3 段の通常探索および4段探索が gate を適用します。5段以上は比例配分へ進むため、この関数で診断行は出ません（`engine/src/program/generate.cpp:7266-7269,7286-7296,7357-7372,7382-7385`）。
- この環境変数があること自体は、候補の採否や gate の有効状態を変えません。startable な候補がない場合に gate を外して再探索する動作も別の `gate_on` 分岐です（`engine/src/program/generate.cpp:7487-7499`）。

## 実行時の詳細

`can_start` は候補ごとの cache slot と prompt buffer の開始可能性を調べます。prompt chunk は `--prefill auto` 相当の設定なら 256-token 単位で最大8192まで二分探索し、それ以外は指定 chunk から256まで半減して探します。各 stage が chunk を cache から貸せない場合は、自前 buffer と追加1536 MiBの余裕を持てるかを確認します（`engine/src/program/generate.cpp:7182-7204,7219-7231`）。

診断フラグは `can_start` 内の関数 static 変数です。最初にこの宣言へ到達した呼び出しで環境変数の有無を読み、そのプロセス内で cache します。以後の環境変更は反映されません（`engine/src/program/generate.cpp:7174-7175,7205-7207`）。環境値の子プロセスへの転送はこの箇所では行いません。

設定時は各 `can_start` 呼び出しにつき、次の形式を stderr に出します。2段探索では `K` に後段の開始 layer、3段以上では `K=0` です。stage ごとの `CUDA%d`、`lb`、`cnt`、`used`、`cap`、`room`、`need`、`slots` は呼び出し時の候補と計算値です（`engine/src/program/generate.cpp:7207-7217`）。

```text
gate: K=%lld chunk=%lld | CUDA%d lb=%lld cnt=%lld used=%lldMiB cap=%lldMiB room=%lldMiB need=%lldMiB slots=%lld
```

診断出力以外の専用ログ、警告、終了・失敗経路はありません。自動探索全体の失敗・fallback はこの変数に関係せず、別の gate 状態や分割候補の有無で決まります（`engine/src/program/generate.cpp:7487-7504`）。性能測定値はこの診断変数について資料に記載されていません。

## 根拠

- `engine/src/program/generate.cpp:4803-4807,4836-4839` — `--serve` と `--layer-split auto` の成立条件、および可視 GPU が一つの場合。
- `engine/src/program/generate.cpp:6959-6961,7174-7189,7191-7204` — 自動探索と startability 判定、chunk の決定。
- `engine/src/program/generate.cpp:7205-7231` — 設定有無の static cache、診断出力、開始可能性の判定。
- `engine/src/program/generate.cpp:7246-7269,7286-7296,7357-7385,7487-7504` — gate と変数の独立性、候補探索範囲、fallback・終了経路。
