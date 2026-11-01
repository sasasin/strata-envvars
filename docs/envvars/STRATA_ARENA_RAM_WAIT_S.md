# `STRATA_ARENA_RAM_WAIT_S`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

通常の expert arena を読み込む前に、arena に必要な RAM が現在の利用可能量を上回っている場合、空き RAM が戻るまで待つ上限秒数を指定します。既定は 20 秒です。待機後も不足が続くときは RAM 不足の警告を記録しますが、それだけを理由に読み込みを拒否しません。値を読むのは Strata 本体の `ArenaExpertSource::open()` です（`src/core/expert_source.cpp:5864-5887`）。

## 値と判定

環境変数を読むのは、利用可能 RAM の取得に成功し、共有 arena でなく、かつ必要量 `need = want + blob` より RAM が少ない場合だけです。`getenv()` が未設定、または値が空文字なら既定の `20.0` 秒のままです（`src/core/expert_source.cpp:5864-5867,5878-5887`）。

空でない値は `std::strtod()` で変換されます。変換が一文字も進まない、文字列末尾まで消費しない、または変換値が `0.0` 未満か `3600.0` を超える場合は無効値として扱い、既定の 20 秒に戻ります。したがって `0` は即時続行、`0.5` は 0.5 秒、`3600` は 1 時間です。負数、3600 超、`abc`、`10s`、末尾に空白などの余分な文字がある値は既定値に戻ります。`strtod` が受け付ける先頭空白や符号は許容されます。`NaN` や無限大は範囲比較を通らないため無効です。変換時の `errno` は検査していません。そのため、`strtod` が underflow で 0 を返し、文字列末尾まで変換した場合も 0 秒として受理されます（同 `src/core/expert_source.cpp:5882-5887`）。

| 設定 | 待機上限 |
|---|---:|
| 未設定・空文字 | 20 秒 |
| 数値として全体を変換でき、0〜3600 の範囲 | 変換値（0 は待機なし） |
| 変換不能・余分な文字・範囲外 | 20 秒 |

CLI 引数や設定ファイルによる上書きは、この読み取り経路にはありません。値は `open()` が RAM 不足を検出した時点で読み取られ、関数内にも static cache はありません。従って、同一プロセスでも `open()` の呼び出しごとに条件を満たせば読み直します。プロセス起動後の環境変更は、次の `open()` がこの分岐に入る場合に限り反映されます。

## 有効になる条件

- expert arena 経路を使用し、通常の arena 読み込みへ進むこと。
- `shared_arena_file` が空であること。`--shared-expert-arena` による共有 arena ではメモリ確認・この環境変数の読み取りをスキップします（`src/core/expert_source.cpp:5863-5865`）。
- `STRATA_ARENA_MMAP` による既存の padded `experts.bin` の読み取り専用 mmap が成功して早期 return していないこと。mmap 成功時はこの待機処理に入りません（`src/core/expert_source.cpp:5822-5854`）。
- OS のメモリ情報取得に成功すること。Linux では `MemAvailable` と可視 cgroup 制限を考慮し、Windows では物理メモリの利用可能量、macOS では free/inactive/purgeable、その他の対応 Unix 系では `_SC_AVPHYS_PAGES` を使います（`src/core/expert_source.cpp:401-508`）。

OS/backend、CLI、モデル状態によって待機秒数自体の解釈が変わる分岐はありません。Linux で cgroup 上限そのものが arena 必要量より小さい場合は、この待機に入る前に `open()` が失敗します。また、利用可能 RAM の測定に失敗した場合はメモリ不足判定ブロックを実行せず、待ちません（`src/core/expert_source.cpp:5864-5877`）。

## 実行時の詳細

`detail::wait_for_ram()` は初回に利用可能 RAM を再測定し、その後 0.25 秒間隔で再測定します。上限に達するまで RAM が戻らなければ終了します。進捗通知間隔は 5 秒です（`src/core/expert_source.cpp:133-149,5890-5901`）。待機中は stderr に次の形式の行を出します（実際の書式文字列）:

```text
strata generate: the expert arena needs ... GiB of RAM and ... GiB is available; waiting up to ... s for it (another engine still exiting?) - ... s so far (STRATA_ARENA_RAM_WAIT_S changes this)
```

必要量に達すると stderr に `strata generate: ... GiB of RAM is available now (after ... s): loading the expert arena` を出します（`src/core/expert_source.cpp:5902-5905`）。時間切れ後も不足なら、`ram_warning_` に必要量・利用可能量・不足量を含む警告を格納し、arena の読み込みへ進みます。利用可能量が必要量の半分未満なら、警告にはメモリ回収でマシン全体が stall する可能性などが加わります（`src/core/expert_source.cpp:5907-5920`）。呼び出し元は読み込み後にこの内容を stderr の `strata generate: WARNING: ...` として出します（`src/program/generate.cpp:6735-6742,6761-6763`）。

`docs/DETAILS.md:711-718` も既定 20 秒、`0` で即時続行、待機後も不足なら警告付きで読み込むと説明しており、実装と一致します。同資料にあるサーバーの旧 engine 終了待ち（最大 120 秒）は別の待機経路であり、この環境変数の対象ではありません。

## 根拠

- 値の既定値、変換、範囲、RAM 不足時の呼び出し: `src/core/expert_source.cpp:5864-5887`
- 待機間隔、再測定、タイムアウト、成功・進捗ログ: `src/core/expert_source.cpp:133-149,5890-5905`
- 不足時の警告内容と続行: `src/core/expert_source.cpp:5907-5920`
- OS ごとの利用可能 RAM の取得: `src/core/expert_source.cpp:401-508`
- 呼び出しと stderr への警告出力: `src/program/generate.cpp:6735-6742,6761-6763`
- 説明資料との照合: `docs/DETAILS.md:711-718`
