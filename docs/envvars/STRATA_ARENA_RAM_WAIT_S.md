# `STRATA_ARENA_RAM_WAIT_S`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`ArenaExpertSource::open` が RAM 上の expert arena を読み込む直前、空き RAM が必要量に足りないときに空き RAM の再確認を続ける最大秒数を指定する。既定は 20 秒、`0` は待たずに次の判定へ進む。待機は RAM を確保したり必要量を減らしたりせず、読み込み元の選択にも単独では影響しない。待機後も不足する場合は、呼び出し側の `--mmap-experts` fallback が有効ならファイル読み込みへ切り替え、無効なら不足警告を残して arena の読み込みを続ける。読み取りは `engine/src/core/expert_source.cpp` の `ArenaExpertSource::open` にある（同ファイル 6445-6447、6560-6604）。

## 値と判定

値は不足分岐に入った時点で `std::getenv` から読み、`std::strtod` で変換する。未設定または空文字なら 20 秒のまま。不正な文字列や範囲外なら明示的なエラーや警告を出さず、やはり 20 秒のまま。変換後の値は `end != w`（少なくとも一文字を変換）かつ `*end == '\0'`（文字列末尾まで消費）かつ `0.0 <= v <= 3600.0` のときだけ採用される（`engine/src/core/expert_source.cpp:6565-6570`）。

| 条件 | unset / 空文字 | 採用される値 | 既定値に戻る例 |
|---|---|---|---|
| RAM 不足の arena 経路 | unset と空文字はいずれも 20 秒 | `strtod` が全体を変換し、値が 0〜3600 秒（両端を含む）。例: `0`、`1`、`20`、`3600` | `-1`、`3601`、`true`、`false`、`0anything`、`20 `、`  ` |

`strtod` のため先頭の空白や符号付き数値は変換可能だが、末尾の空白・文字は全体一致条件を満たさない。大文字小文字の真偽値比較はない。`errno` は調べず、範囲条件だけで採否を決める。範囲内の `0` は採用されるが、待機関数を呼ぶ条件が `wait_s > 0.0` のため直ちに待機を省略する（同ファイル 6566-6574）。CLI にこの秒数を上書きする引数はなく、arena 不足時の判定における RAM 量や fallback 可否は別の条件で決まる（同ファイル 6533-6537、6590-6604）。

## 有効になる条件

- 実行経路が `ArenaExpertSource::open` による RAM arena の構築であること。generate 側は `o.mmap_experts` が false のとき arena を開く（`engine/src/program/generate.cpp:8548-8550、8799-8801`）。最初から `--mmap-experts` を選んだ実行は対象外。
- `experts.bin` が `STRATA_ARENA_MMAP` によって正常に読み取り専用 mmap され、`open` が早期 return しないこと。Windows ではこの mmap 分岐自体を無効化している（`engine/src/core/expert_source.cpp:6490-6523`）。
- `shared_arena_file` が空で、`host_available_memory` が RAM 情報を取得できること。共有 arena のとき、または RAM 情報を取得できないときは RAM 判定ブロックに入らず、この変数も読まれない（同ファイル 6533）。
- cgroup の hard memory limit が arena の必要量を満たすこと。hard limit による拒否または fallback 判定が先に行われるため、その分岐では待機しない（同ファイル 6543-6559）。
- RAM の空きが arena 必要量より少ないこと。十分なら待機も変数の読み取りも行わない（同ファイル 6560-6566）。
- プロセス実行中に環境を変更しても、この分岐で読み取った後の待機には反映されない。起動時の static cache はなく、該当する `open` 呼び出しごとに不足時だけ読む（同ファイル 6566-6574）。

RAM が不足して待機が終わった後も、`give_back_ram` callback があれば RAM を返す処理を行い、空き量を再取得してから不足を判定する。CLI 側では `--ple-io ram` を明示した場合、共有 arena 指定時、または `STRATA_ARENA_RAM_FALLBACK=0` の場合など fallback が許可されない。fallback が許可され、なお不足する場合は `--mmap-experts` 相当へ切り替える（`engine/src/program/generate.cpp:8526-8534、8788-8801、8805-8829`）。

## 実行時の詳細

不足時は `detail::wait_for_ram(need, wait_s, 0.25, 5.0, ...)` を呼ぶ。空き RAM を 0.25 秒間隔で再取得し、最大時間まで待つ。待機中は最初の確認時と以降 5 秒ごとに進捗ログを出す。必要量に届けば arena の読み込みへ進み、届かなければ `give_back_ram` がある場合はそれを実行し、もう一度 RAM を調べる（`engine/src/core/expert_source.cpp:6571-6604`。待機ループは同ファイル 146-162）。

`STRATA_ARENA_RAM_WAIT_S=0` または有効な小数値は待機時間だけを変える。最終的な不足時に fallback するかは `fall_back_when_ram_short` に従い、許可時は `open` が false と `ram_short_` を返して呼び出し側がファイル経路を選ぶ。許可されない場合は arena の読み込みを続け、RAM 不足警告を記録する（`engine/src/core/expert_source.cpp:6604-6676`; `engine/src/program/generate.cpp:8805-8829`）。

## ログと測定値

待機に入ると stderr に次の形式で出る。`wait_s` と `waited` は `%.0f` で表示されるため、ログ上は秒未満が丸められる。

```text
strata generate: the expert arena needs ... GiB of RAM... and ... GiB is available; waiting up to ... s for it (another engine still exiting?) - ... s so far (STRATA_ARENA_RAM_WAIT_S changes this)
```

必要量に届いた場合は stderr に `strata generate: ... GiB of RAM is available now (after ... s): loading the expert arena` と出る（`engine/src/core/expert_source.cpp:6578-6588`）。`0` の場合は待機進捗・待機成功ログを出さない。タイムアウト後も不足し fallback 可能なら、generate は stderr に `strata generate: not enough RAM for the expert arena (...)` と出し、`--serve` の場合は同じ案内を stdout にも出してファイル読み込みへ切り替える。fallback が許可されない場合の不足警告文は `the expert arena needs ...` で、空き量が必要量の半分未満ならメモリー回収による停止の説明が追加される（`engine/src/program/generate.cpp:8805-8819`; `engine/src/core/expert_source.cpp:6663-6674`）。

`docs/DETAILS.md:848-855` は既定 20 秒、`0` で即時に次へ進むことと、別 engine の終了待ちを説明している。ソースでは環境変数に 0〜3600 秒の上限があり、待機後も不足する場合は条件に応じて fallback または警告付き読み込みとなる。

## 根拠

- 値の読み取り・変換・範囲・待機呼び出し・ログ: `engine/src/core/expert_source.cpp:6560-6588`
- 空き RAM の再確認ループ: `engine/src/core/expert_source.cpp:146-162`
- hard limit と不足後の fallback / 警告経路: `engine/src/core/expert_source.cpp:6533-6559、6590-6676`
- arena 呼び出し条件と RAM fallback の設定: `engine/src/program/generate.cpp:8524-8547、8788-8829`
- 説明資料との照合: `docs/DETAILS.md:848-855`
