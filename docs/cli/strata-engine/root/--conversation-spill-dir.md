# `strata --conversation-spill-dir`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（推論エンジン。`--serve` で常駐サーバーとして起動） |
| オプション | `--conversation-spill-dir` |
| 別名 | なし |
| 値 | `PATH`。会話キャッシュの SSD tier のルートディレクトリ |

## 役割

`--serve` の会話キャッシュで、RAM から退避する会話を保存する SSD tier のルートを指定する。会話キャッシュが有効で、単一 stage で、`--conversation-spill-mib` が 0 でない場合に tier の初期化を試みる。指定がない場合は `--pack` が `<data>/packs/<tag>` 配下にあるとき `<data>/conversation-spill` を使うが、このオプションを指定するとその場所を優先する（`engine/src/program/generate.cpp:1110-1114,13965-13978`）。

## 使い方

```sh
# サーバーの会話退避先を指定する
strata --pack /srv/strata-data/packs/model --serve --conversation-spill-dir /var/cache/strata/conversations
```

このパスはディレクトリとして作成・使用される。会話 spill tier 自体は RAM tier が退避または受け入れ拒否した会話を対象とし、RAM に収まる会話はディスクへ書かない（`engine/src/program/generate.cpp:13956-13961`）。

## 値と既定値

- `PATH` は文字列として保存される。parser 側で存在確認、正規化、空文字の拒否は行わず、重複指定時は引数列を処理する順で後の値が前の値を置き換える（`engine/src/program/generate.cpp:4104-4105`）。
- 未指定時の保存先は、`--pack` のパスが `<data>/packs/<tag>` の形なら `<data>/conversation-spill`。それ以外でこのオプションも未指定なら root が決まらず tier は無効になる（`engine/src/program/generate.cpp:13967-13978`）。
- 空文字は空のまま保持され、明示的な保存先としては使われず、未指定時と同じ自動選択経路に入る（`engine/src/program/generate.cpp:13967-13978`）。
- parser に値の書式・範囲 validation はない。ディレクトリの作成、利用可能なディスク容量の取得、spill namespace のオープンは初期化時に行われ、使用できない場合は tier が有効にならず stderr に理由が出る（`engine/src/program/generate.cpp:13979-14012`, `engine/include/strata/core/conversation_spill.hpp:175-217`）。

## 実行時の動作

指定した root の下に engine process 用の namespace が作られる。容量は `--conversation-spill-mib` が正なら指定 MiB と空き容量から予約床を差し引いた量の小さい方、0 または未指定（内部既定 `-1`）なら最大 32 GiB・空き容量の 25%・予約床を守る範囲で決まる。予約床は `--session-min-free-mib`（既定 4096 MiB）の値で、負値は 0 として扱われる。計算後の容量が 64 MiB 未満なら tier は無効化される（`engine/src/program/generate.cpp:1108-1120,13979-13987`; `engine/include/strata/core/conversation_spill.hpp:57-64`）。

root は `std::filesystem::create_directories` で作成される。永続化用の `--conversation-spill-persist` が指定されていなければ、namespace はプロセス終了時に削除され、異常終了後に残った namespace は後続起動時の cleanup 対象になる。永続化が有効なら fingerprint 用の安定 namespace を使用し、既存の同一モデル・設定の会話を採用する。したがって、指定パスと永続化設定は保存場所・再起動後の保持に関係する（`engine/src/program/generate.cpp:13991-14009`; `engine/include/strata/core/conversation_spill.hpp:163-229,284-301`）。

## 適用条件と副作用

- 会話キャッシュが有効、layer split の stage が空（単一 stage）、かつ `--conversation-spill-mib 0` でない場合に限り初期化される。別条件ではこの指定先を使った tier 初期化は行われない（`engine/src/program/generate.cpp:13956-13978`）。
- 指定 root が作成され、ディスク容量確認に使われる。容量確認に失敗した場合、空き容量が予約床以下の場合、spill namespace を開けない場合は tier を有効化せず、stderr に理由を出す。engine の起動全体をこの理由だけで失敗させる経路ではなく、tier を使わず継続する（`engine/src/program/generate.cpp:13979-14012`; `engine/include/strata/core/conversation_spill.hpp:175-217`）。
- 永続化なしでは orderly shutdown 時に自プロセスの namespace を削除する。永続化ありでは安定 namespace の既存内容を調べ、現在のモデル・設定と一致しないファイル等を削除する。また persistent namespace を他 engine が保持中なら、このプロセスは個別 namespace に fallback する（`engine/include/strata/core/conversation_spill.hpp:172-225,284-301,528-585`）。
- spill 対象は再読込より SSD 往復が得になると判定された会話に限られる。書き込み成功・失敗・tier 無効化の状況は stderr に記録される（`engine/src/program/generate.cpp:14014-14046,14048-14073`）。

## 出力とエラー

有効化時は利用中の namespace と容量を stderr に表示する。初期化できない場合は `no SSD tier` と理由を表示する。個別会話の書き込み成功・失敗も stderr に記録される（`engine/src/program/generate.cpp:14001-14012,14048-14073`）。

このオプション自体の parser は、値の内容に対する validation error を定義していない。未知の引数は usage とともに終了コード 2 で拒否される（`engine/src/program/generate.cpp:4104-4105,4263-4268`）。

## 根拠

- `engine/src/program/generate.cpp:1110-1120` — オプション値の保持、関連する spill 容量・永続化設定と既定値。
- `engine/src/program/generate.cpp:4104-4105` — parser 登録と引数値の格納。
- `engine/src/program/generate.cpp:13956-14013` — 適用条件、root 選択、容量計算、初期化結果と stderr 出力。
- `engine/src/program/generate.cpp:14014-14073` — 会話を spill する条件と書き込み結果のログ。
- `engine/include/strata/core/conversation_spill.hpp:57-64,163-229,284-301,528-601` — 既定容量計算、namespace の作成・cleanup・永続化・既存エントリ採用。
