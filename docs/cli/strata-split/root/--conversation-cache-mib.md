# `--conversation-cache-mib`

調査対象: Strata commit `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-split` |
| コマンド | `strata-split-N`（N はビルド対象のカード数。サブコマンドなし） |
| オプション | `--conversation-cache-mib` |
| 別名 | なし |
| 値 | MiB 単位の整数。parser は `std::stol` で `long` に変換する |

## 役割

会話キャッシュに使うホストメモリの予算を MiB で指定します。会話状態を GPU 上の K/V pool からホストメモリへ退避し、次の会話ターンで再利用する処理と、会話途中の checkpoint の保持にこの予算が使われます。ここでの値は `strata-split-N` の設定であり、同名の通常 `strata` エンジン用オプションとは別スコープです（`src/split/tools/sfnx.cpp:65-70,72-104`）。

## 使い方

```sh
strata-split-2 --serve --native model.gguf --mtp draft-layer --conversation-cache-mib 4096
```

`--serve`、`--native`、`--mtp` はこの実行ファイルの起動に必要です。カード数に対応する `strata-split-N` はビルド時に選ばれます（`src/split/tools/sfnx.cpp:4-5,100-102`、`src/split/CMakeLists.txt:92-97`）。

## 値と既定値

- 省略時は `0` です。0 バイト予算となり、会話の park/cache を行いません（`src/split/tools/sfnx.cpp:65-70,435-440`、`src/split/src/session.cpp:154-162,308-312`）。
- 指定値は `std::stol` で `long` に変換され、その値を `size_t` に変換してから `1 MiB = 2^20` バイトを掛けるシフトで byte 予算にします（`src/split/tools/sfnx.cpp:72-89,435-438`）。
- `std::stol` には変換位置の検査が渡されていないため、数値の後ろに変換されない文字が続いても数値部分が受理されます。数値部分がない値や `long` の範囲外は変換例外になります（`src/split/tools/sfnx.cpp:76-79,88`）。
- オプション値の非負範囲や上限を検査する処理はありません。負数は拒否されず `size_t` へ変換されてからシフトされます。したがって負数を有効な予算として使うことはできず、意図した上限にならない可能性があります（`src/split/tools/sfnx.cpp:88,435-438`）。
- 同じオプションを複数回指定した場合は、引数走査中に `cache_mib` を上書きするため最後の値が残ります（`src/split/tools/sfnx.cpp:74-89`）。

## 実行時の動作

起動時に作られる `ConvCache` の共有予算を、この値から byte 単位で設定します。複数 slot の `Session` は同じ cache を共有します。会話状態を保持する際、予算を超えると最も古く使われた parked conversation を順に追い出し、それでも超える場合は live conversation の checkpoint を古い順に削除します（`src/split/tools/sfnx.cpp:435-455`、`src/split/src/session.cpp:350-361`）。

会話状態の park は、cache 予算が 0 より大きく、会話履歴が 1024 token 以上のときに行われます。K/V pool の空きが不足した場合、または arena が expert に貸し出されている間に slot が長時間 idle になった場合、idle conversation の状態をホストメモリへ退避して lane の pool pages を返します。退避や復元、追い出しは stderr に `conversation cache:` または `sfnx:` の診断行を出します（`src/split/src/session.cpp:15-20,308-330`、`src/split/tools/sfnx.cpp:394-432`）。

Strata の split-engine 起動設定は `split_config()` の既定 `cache_mib=4096` を引数として明示的に渡します。そのため通常の split-engine 経由では、エンジン単体 parser の既定 `0` ではなく 4096 MiB が使われます（`strata_control/split_engine.py:73-80,250-263`）。

## 適用条件と副作用

このオプションは `strata-split-N` にだけ適用されます。Terminal の launch が split-engine を選び、その構成を生成するときに値が渡されます。split-engine の適用可否や通常 engine への fallback は別の判定経路です（`strata_cli/launch/runner.py:1630-1637,1662-1682`、`strata_control/split_engine.py:250-264,480-510`）。

予算はホストメモリ上で保持する会話状態と checkpoint の上限です。会話状態を退避する処理では engine state を保存し、元の lane を reset して K/V pool pages を返します。上限に達したときの追い出しは会話の再利用可能性を減らします（`src/split/src/session.hpp:77-91,109-115`、`src/split/src/session.cpp:308-338,350-361`）。ソース上、この値分のメモリを起動時に事前確保する処理は確認できません。

## 出力とエラー

- オプション値が欠けると `--conversation-cache-mib needs a value`、変換できない値や `long` 範囲外の値では標準ライブラリの変換例外になります。引数解析時の例外は stderr に `sfnx: <理由>` と出して終了コード `2` になります（`src/split/tools/sfnx.cpp:76-79,88,1040-1048`）。
- 起動成功後、標準出力の `INFO` 行に `conversation_cache_mib=<指定値>` が出ます（`src/split/tools/sfnx.cpp:1081-1083`）。
- モデルや engine のロード後など、引数解析後の例外は `ERR <理由>` を標準出力、`sfnx: failed: <理由>` を標準エラーに出し、終了コード `1` で終了します。これは引数変換以外も含む一般的な失敗経路です（`src/split/tools/sfnx.cpp:1027-1035,1050-1065,1086-1092`）。

## 調査範囲

同一 revision の parser、cache 予算の設定、cache 保持・eviction、launch から split 設定を作る箇所を確認しました。安全に起動できる同一 revision の実行バイナリは確認していないため、`--help` 出力との照合は行っていません。負数や数値サフィックスの挙動は parser の変換コードから記述しており、実バイナリでの動作確認はしていません。

## 根拠

- `src/split/tools/sfnx.cpp:65-104` — parser の既定値、値変換、必須引数と batch validation。
- `src/split/tools/sfnx.cpp:435-455,1040-1048,1081-1083` — byte 予算の設定、parse 失敗、起動時 INFO。
- `src/split/tools/sfnx.cpp:394-432` — pool 不足・idle 時の会話 park。
- `src/split/src/session.hpp:77-100,109-115` — cache の共有単位と会話状態の説明。
- `src/split/src/session.cpp:154-162,308-330,350-361` — cache 有効条件、park、eviction と checkpoint 削除。
- `strata_control/split_engine.py:73-80,250-264` — split-engine 構成が既定 4096 MiB を引数へ渡す処理。
- `strata_cli/launch/runner.py:1630-1637,1662-1682` — launch から split-engine を適用する経路。
- `src/split/CMakeLists.txt:92-97` — `strata-split-N` の製品 target。
