# `CORE`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`CORE` は Strata 本体の実行時設定ではなく、Linux HIP 用の engine package を作る packaging shell script が共有ライブラリの検索先として受け取る環境変数です。`packaging/build_hip_linux.sh` と `packaging/build_dsv41_hip_linux.sh` は値を `CORE` として保持し、バイナリに必要なライブラリを stage folder に集める `packaging/collect_libs.py` へ検索ディレクトリを渡します（`packaging/build_hip_linux.sh:5-12,27,97-104`; `packaging/build_dsv41_hip_linux.sh:8-9,19,66-69`）。

Strata の通常の engine / server / CLI ソースに `CORE` を読む箇所は見つかりませんでした。この変数が影響するのは、これらの packaging script を実行してパッケージを組み立てる時点です。

## 値と判定

両 script とも `set -u` の下で `CORE=${CORE:-$HP}` と代入します。`${name:-word}` は未設定または空文字の場合に `word` を使うため、`CORE` を省略した場合と `CORE=''` の場合はどちらも必須入力 `HP` の値に置き換わります。空でない値は文字列としてそのまま使われます。パスの存在、形式、絶対パスかどうかの検査や文字列の変換はありません（`packaging/build_hip_linux.sh:22-28`; `packaging/build_dsv41_hip_linux.sh:14-20`）。

| 入力 | script 内の `CORE` |
|---|---|
| 未設定 | `$HP` |
| 空文字 | `$HP` |
| 空でない値 | 指定された値 |

`HP` 自体は必須で、未設定なら `HP=<ROCm devel root>` のパラメータ展開で script が終了します。CLI option による `CORE` の上書きはありません（`packaging/build_hip_linux.sh:25-28`; `packaging/build_dsv41_hip_linux.sh:17-20`）。

## 有効になる条件

- Linux HIP engine package の `packaging/build_hip_linux.sh` を実行し、library collection の段階に到達した場合に使われます。`VISION_ONLY` が非空なら reader だけを作ってその前に終了するため、`CORE` は collection に使われません（`packaging/build_hip_linux.sh:91-104`）。
- DeepSeek-V4.1 専用 package の `packaging/build_dsv41_hip_linux.sh` では、build 完了後の collection で使われます（`packaging/build_dsv41_hip_linux.sh:66-69`）。
- `build_hip_linux.sh` では `DSV41` が有効な場合も同じ `CORE` 検索先が `strata-dsv41` の collection に使われます。無効な場合はそのバイナリを collection 対象に加えません（`packaging/build_hip_linux.sh:68-76,97-104`）。
- `LIBW` は別の入力で、未設定・空文字なら `$HP` になります。collector には `LIBW/lib`、`HP/lib`、`CORE/lib`、`CORE/lib/llvm/lib` の順で検索先が渡され、`HP/lib/rocm_sysdeps/lib` はそのディレクトリがある場合に追加されます（`packaging/build_hip_linux.sh:26-28,54-56,97-103`; `packaging/build_dsv41_hip_linux.sh:18-20,40-42,66-68`）。

## 実行時の詳細

各 shell script の開始時に `CORE` を一度 shell 変数へ代入し、library collection 時に `$CORE/lib` と `$CORE/lib/llvm/lib` を `collect_libs.py --search` 引数として展開します。起動後に親プロセス側の環境変数を書き換えても、すでに起動した shell の値は再読込されません。script はその値を engine の実行環境へ設定・転送せず、package 作成のための collector 引数にのみ使います（`packaging/build_hip_linux.sh:27,101-103`; `packaging/build_dsv41_hip_linux.sh:19,66-68`）。

collector は `--search` の値を使って `LD_LIBRARY_PATH` を組み立て、`ldd` に渡します。依存ライブラリが解決できない場合は `collect.log` に `WARNING: <binary> needs <name>, which ldd cannot find` を出します。collection コマンドの非 0 終了は `chk` が status file に記録して build を中断しますが、未解決依存の警告自体は collector の終了コードを非 0 にする処理ではありません（`packaging/collect_libs.py:85-98,122-125`; `packaging/build_hip_linux.sh:47-48,101-104`; `packaging/build_dsv41_hip_linux.sh:35,66-69`）。この記述は Strata の script が検索先を渡し、collector が警告を出す経路についてであり、`ldd` や動的 linker 自体の挙動を説明するものではありません。

## 根拠

- 候補一覧には `CORE` が含まれます（`docs/envvars/000_envvers.md:121`）。ソース全体の完全一致参照を調べると、環境から値を設定する箇所は上記 2 本の packaging script でした。その他の一致は `lscpu` の CSV 列 `CORE` と C++ の「core」コメントで、環境変数の読み取りではありません（`apps/host/server/hardware.mjs:123`; `src/kernels/cpu/pool.cpp:401`）。
- package 作成 script の概要は `packaging/README.md:32` にあります。実装の値判定、検索先の組み立て、collector の警告・終了経路は上記の Strata 所有 source を根拠にしています。
