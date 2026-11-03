# `FNX_DUMP_FIRST_LOGITS`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。調査開始時の作業ツリーは `main...origin/main` で、未コミット変更はありませんでした。外部ライブラリの環境変数は対象外です。

## 役割

sFNX split engine の各 `Session::generate()` で、最初の verify が終わった直後に全語彙の logits 行を float32 のバイナリファイルへ書き出す診断用フックです。環境変数の値は出力先パスの接頭辞として使われ、連番を付けた `<値>.<番号>` が出力ファイル名になります。通常の `strata` 実行全般を制御する設定ではなく、ビルド時に opt-in する `strata-split` の session 実装に限られます。

## 値と判定

| 環境値 | 動作 |
|---|---|
| 未設定 | 出力しない。`getenv()` は null となり、書き出し分岐に入りません。 |
| 空文字 | 設定済みとして扱う。パスは `.0`, `.1`, ... となり、実行時の作業ディレクトリー直下に作られます。 |
| 空でない任意の文字列 | 文字列全体をパス接頭辞にし、末尾に `.` と番号を付けます。真偽文字列や数値への変換・検証はありません。 |

相対パス・絶対パスのどちらも特別扱いせず `fopen()` に渡します。CLI 引数や別の環境変数による優先順位、範囲制限、無効値時の fallback はありません。読み取り結果のポインターとファイル番号は関数内の `static` に保持されるため、環境値はプロセス内でこの箇所に初めて到達した時に読み取られ、その後の呼び出しで再読込されません。番号もプロセス内で共有され、書き込みを試みるたびに開く前に増加します。

## 有効になる条件

- `STRATA_BUILD_SPLIT=ON` で split engine をビルドする必要があります。既定は OFF です。ビルド対象は Linux CUDA または Linux HIP で、さらに `STRATA_GGML_DIR` が必要です。CUDA 側は split engine が組み込まれ、HIP 側も同じ `session.cpp` を HIP ソースとしてビルドします (`CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-7,20-30,64-77,92-120`)。
- 実行時に `Session::generate()` が呼ばれ、`produced == 0` のまま最初の `e_.verify(rows)` が戻る必要があります。検証より前に停止した経路ではこの出力箇所に到達しません (`src/split/src/session.cpp:397-404,452-477`)。
- sFNX server では request を処理する `generate` 経路から呼び出されます (`src/split/tools/sfnx.cpp:839-847`)。通常の Strata server / CLI にこの読み取りがあることは確認できません。

環境値が設定されている場合、各 `generate()` 呼び出しの最初の verify 行を対象にします。`produced` は呼び出しごとに 0 から始まり、token の emit 後に増えるため、同じ `Session` で続けて `generate()` を呼ぶ場合も呼び出しごとに対象になります (`src/split/src/session.cpp:403,466-477,531-545`)。

## 実行時の詳細

最初の verify の後に `e_.last_logits(1)` を呼び、その戻り値の全要素を `fwrite` で出力します。Engine の API コメントは `last_logits(T)` を、直近の window における全語彙の logits（T 行）としています (`src/split/src/session.cpp:466-472`, `src/split/src/engine.hpp:46-53`)。ファイルは `wb` モードで開かれるため、同じパスが既にあれば切り詰められます。連番は通常の同一プロセス内では異なります。出力にはヘッダーや要素数は付かず、各値は 4 byte の float32 として書き込まれます (`src/split/src/session.cpp:471-475`)。

`fopen()` が失敗した場合、または `fwrite()` が全要素を書けなかった場合は stderr に `session: FNX_DUMP_FIRST_LOGITS: cannot write <path>` を出します。例外や生成の中断にはせず、開けていたファイルは閉じます。`fclose()` の戻り値は検査しません (`src/split/src/session.cpp:472-475`)。環境値が未設定ならログもファイル出力もありません。

## 根拠

- 読み取り、初回 verify 後の実行条件、連番、logits 取得、ファイル書き込みと stderr 警告: `src/split/src/session.cpp:397-404,452-477,531-545`
- Engine が返す logits 行の説明: `src/split/src/engine.hpp:46-53`
- sFNX server の request から `Session::generate()` への呼び出し: `src/split/tools/sfnx.cpp:839-847`
- split engine の opt-in、対応 OS/backend、`session.cpp` のビルド対象: `CMakeLists.txt:2945-2949`, `src/split/CMakeLists.txt:1-7,20-30,64-77,92-120`
