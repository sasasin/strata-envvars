# `STRATA_IO_PREFETCH_DEPTH`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-12 時点）。外部ライブラリの環境変数は対象外。

## 役割

ルーティング予測による先読みで、現在の層の入力から何層先まで expert を予測して warm するかを指定します。予測はファイル層や Foresight swap space の先読み用で、実際に計算する expert の選択を変えません。

## 値と判定

| 設定値 | 動作 |
|---|---|
| 未設定、空文字、`atoi` の結果が 0 以下 | ファイルI/O prefetch が有効なら2層。そうでなければ `RouterLookahead` の初期値1層 |
| `atoi` の結果が正 | `set_depth()` に渡し、1〜4に制限 |

文字列全体の妥当性検査はなく、C/C++ の `std::atoi` で整数変換します。したがって、先頭の空白や符号を含む数値部分が変換され、後続の非数値部分は判定に使われません（例: `2junk` は2）。数値に変換できない文字列は0となり、既定値の経路に入ります。正の値は4を超えていても4、0や負値は明示値として採用されず既定値になります。

## 有効になる条件

変数は CUDA/HIP 側の `src/program/generate.cpp` で、ルーティング先読みが正常に開始した後に読み取られます。先読み開始には、source があること、`STRATA_LOOKAHEAD` が未設定または `atoi` で0以外であること、ルーター重みを BF16 として arena から読み出せることなどが必要です。通常は source が `warms()` を提供する場合に開始し、Foresight 先読みまたは統計計測が有効な場合にも開始経路があります。条件を満たさない場合、この変数の値は使われません。

`STRATA_IO_PREFETCH` が有効な場合、その本体は Linux の mapped file tier 用です。ただし `STRATA_IO_PREFETCH_DEPTH` 自体の読取箇所に OS ガードはなく、正常に開始した routing lookahead の深さを設定します。たとえば Foresight 先読みや統計計測で lookahead が開始する経路でも、正の明示値が適用されます。SYCL の `sycl/src/program/generate.cpp` は別の開始処理を持ち、この環境変数を読みません。

## 実行時の詳細

設定は generate の初期化時に一度読み取られます。実行中に環境を書き換えて深さを更新する処理はありません。

各 dispatch で lookahead は最大8 token 分の現在層入力を保存し、予測スレッドへ送ります。スレッドは `layer + 1` から始め、設定された深さの範囲内で各層の router と同じ入力を使って expert を順位付けします。各層で GPU cache にある expert を除いた top-k を source に warm させます。層数の末尾を超える予測は行いません。また、先行する予測がまだ実行中または待機中なら、その dispatch の予測はスキップされます。

ファイルI/O prefetch 有効時に深さの指定がない場合は2層となり、明示的な正値があればその値（最大4）が優先します。Foresight swap space への予測転送は、深い予測が不正確になりやすいとして最初の予測層だけに限定されています。統計計測も最初の予測層を採点します。起動時には routing-aware prefetch の有効・無効ログが出ますが、深さの実値を示すログはありません。

## 根拠

- `src/program/generate.cpp:5491-5523` — lookahead の有効条件、router 重みの読み出し、`STRATA_IO_PREFETCH_DEPTH` の読み取り、値なしの場合の深さ2既定値。
- `include/strata/core/expert_source.hpp:259-265,281` — lookahead の深さ初期値1、setter の1〜4 clamp。
- `src/core/expert_source.cpp:2202-2214,2312-2336,2367-2412` — dispatch の入力保存、深さ分の層予測、top-k の非resident expert の warm、Foresight 転送を最初の層だけにする処理。
- `src/core/expert_source.cpp:3634-3639` — dispatch ごとの非同期 submit と統計採点。
- `sycl/src/program/generate.cpp:5081-5095` — SYCL 側の lookahead 開始処理にこの変数の読み取りがないこと。
- `docs/DETAILS.md:225-232` — Linux file-tier I/O の説明。I/O prefetch 有効時の予測層数の既定値を2として記載。
