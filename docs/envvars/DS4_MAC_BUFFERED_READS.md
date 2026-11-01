# `DS4_MAC_BUFFERED_READS`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

macOS で GGUF shard 用の direct-read descriptor を開くとき、`F_NOCACHE` を設定する `fcntl()` 呼び出しを省略します。変数名は buffered reads を示しますが、Strata が行うのは `F_NOCACHE` の要求を出さないことです。OS がその descriptor の読み取りをどう扱うかまでは、この変数の実装から断定できません。

## 値と判定

値の内容は parse されず、`std::getenv()` の null 判定だけを行います。

| macOS での値 | Strata の処理 |
|---|---|
| 未設定 | `fcntl(fd, F_NOCACHE, 1)` を呼ぶ |
| 設定あり（空文字を含む） | `fcntl()` を呼ばない |

`0`、`1`、その他の文字列に差はありません。数値変換、境界値、無効値の検査、CLI 引数との優先順位はありません。`fcntl()` の戻り値も検査されず、失敗時の警告や fallback はこの箇所にはありません。

## 有効になる条件

- `open_direct()` の非 Windows 経路のうち、`__APPLE__` が定義されたビルドだけで判定されます。macOS では `O_DIRECT` が通常存在しないため、Strata 同梱の `ds4_os_apple.h` は未定義の場合に `O_DIRECT` を `0` と定義しています。
- `Pack::load()` がモデル形式を GGUF と判定した場合、各 shard に対して `open_direct()` を呼びます。モデル形式が GGUF でなければ、この descriptor は開かれません。
- 開いた descriptor が実際の読み取り候補になるのは `direct_reads` が有効になった後です。`DS4_NO_VIEW` の値が `atoi(...) != 0` なら no-view 経路を要求しますが、さらに `store` が存在し `pk.gguf` が真である必要があります。自動で no-view を選ぶ分岐は Windows HIP APU 向けの条件付きコードで、macOS には適用されません。
- したがって通常の mmap view を保持する経路では、GGUF 用 descriptor は作られていても、この変数による設定差は読み取り経路に現れません。

## 実行時の詳細

環境変数は各 `open_direct()` 呼び出し時に読み直され、結果を static cache しません。GGUF shard の descriptor は `Pack::load()` 時に開かれます。その後 `drop_views()` が実行されると mmap view を外し、`direct_reads` を有効にします。以降の `read_at()` は、有効な direct descriptor がある場合に `pread_direct()` を試します。direct read が失敗すると `pread_par()`、それも使えない場合は `pread_full()` に進みます。この fallback はこの環境変数の設定有無では分岐しません。

この変数専用のログ、終了、エラー経路はありません。no-view 経路が選ばれた場合の stderr は `ds4: no view of the model's files after the load: unbuffered reads at the drive's rate` です。読み取りが最終的に失敗した場合は呼び出し側が通常の読み込み失敗を返し、たとえば expert 読み込みでは `reading layer ...'s experts from the model's files failed` を設定します。`DS4_MAC_BUFFERED_READS` 自体がその文言を出すわけではありません。

## 根拠

- 変数名の唯一の実参照と macOS 条件、値判定、`fcntl()` 呼び出し: `src/dsv41/ds4_os.hpp:82-103`。
- macOS で `O_DIRECT` を `0` とする定義: `src/dsv41/ds4_os_apple.h:19-23`。
- GGUF shard ごとの direct descriptor 作成: `src/dsv41/ds4_model.cu:386-403`。
- direct read と buffered fallback の順序、view を落とした後に direct read を有効化する処理: `src/dsv41/ds4_model.cu:455-497`。
- no-view の条件、Windows HIP APU のみの自動選択、観測ログ: `src/dsv41/ds4_model.cu:3186-3200`。
- expert 読み込み失敗の呼び出し側メッセージ: `src/dsv41/ds4_model.cu:3747-3759`。

