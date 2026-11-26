# `STRATA_POOL_UMWAIT_C02`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CPU `ExpertPool` の worker が仕事待ちで `UMWAIT` 命令を使う場合、その待機状態を C0.1（浅い状態）から C0.2（より深い状態）に選びます。この変数だけでは `UMWAIT` を有効にしません。`STRATA_POOL_UMWAIT` に正の TSC サイクル数を設定し、対応するビルドと CPU であることが必要です。処理する仕事や worker 数を変える設定ではなく、worker の待機ループ内で `_umwait` に渡す状態値を変えます（`engine/src/kernels/cpu/pool.cpp:40-44,64-66,1088-1102`）。

## 値と判定

`umwait_state()` の関数内 `static` 初期化で `std::getenv` の値を読み、値が存在し、先頭文字が ASCII `'1'` なら `0`（C0.2）、それ以外なら `1`（C0.1）を返します。文字列全体や数値としての妥当性は検査しません。大文字小文字や空白の正規化もありません（`engine/src/kernels/cpu/pool.cpp:64-66`）。

| 条件 | unset | C0.2 になる値 | C0.2 にならない値 |
|---|---|---|---|
| `umwait_state()` が呼ばれる経路 | C0.1 | `1`, `10`, `1anything` など先頭が `1` | 空文字、`0`, `true`, ` 1`, `-1`, `anything` など先頭が `1` 以外 |

この表は C02 判定だけの結果です。実際には `STRATA_POOL_UMWAIT` がない、空、`0`、負値、または数値として正にならない値なら `UMWAIT` 経路自体に入りません（`std::atoll` の結果が `<= 0`）。その場合は C02 の値に関係なく従来の `strata_cpu_pause()` による待機です（`engine/src/kernels/cpu/pool.cpp:45-49,1090-1102`）。

## 有効になる条件

- `engine/src/kernels/cpu/pool.cpp` がビルドされ、`ExpertPool` worker が実行されている必要があります。CPU kernel library には x86 と portable の両構成で `pool.cpp` が含まれます（`engine/cmake/backends/cpu.cmake:241-246`）。
- `UMWAIT` 命令を使うコードは `_MSC_VER && _M_X64 && !__clang__` のビルドに限られます。つまり MSVC x64（clang-cl を除く）でのみ対象変数が実動作に影響し、それ以外では `umwait_cycles()` が 0 を返して worker は spin します（`engine/src/kernels/cpu/pool.cpp:49-60,1084,1090-1102`）。
- 上記ビルドでも `STRATA_POOL_UMWAIT` の `std::atoll` 結果が正でなければ C02 判定は使われません。正なら Strata が CPUID leaf 7 の WAITPKG bit を確認します。bit がなければ stderr に `strata: STRATA_POOL_UMWAIT: this CPU has no WAITPKG, the workers spin` と出し、spin に戻ります（`engine/src/kernels/cpu/pool.cpp:45-57`）。
- `STRATA_POOL_UMWAIT_ESC` の変換結果が正の場合、各 park の経過サイクルに応じて最初は状態 `1`、指定サイクル後は状態 `0` を選びます。この経路では `umwait_state()` を呼ばないため `STRATA_POOL_UMWAIT_C02` は読まれず、状態を上書きしません（`engine/src/kernels/cpu/pool.cpp:68-72,1084-1096`）。未設定、空、または `atoll` 結果が 0 以下ならこのエスカレーションはなく、C02 の判定が使われます。
- CLI 引数や設定ファイルによる C02 値の上書きは、Strata ソース内に見つかりません。対象名のコード上の読み取りはこの `getenv` 一か所です（同ファイルのコメントにも説明上の記載があります）。ほかに Terminal の `settings-register.json` に登録情報がありますが、環境値を読む実装ではありません。

## 実行時の詳細

生成経路は `generate.cpp` で `ExpertPool` を構築し、pool.cpp の各 worker が仕事を取りに行く前に待機ループへ入ります（`engine/src/program/generate.cpp:9001-9008`, `engine/src/kernels/cpu/pool.cpp:1062-1089`）。仕事がなければ epoch 値を見て待ちます。`STRATA_POOL_UMWAIT` が有効な場合、worker は epoch のアドレスを監視し、epoch が変わっていなければ現在の状態値と期限（現在の TSC + 指定 cycle 数）を `_umwait` に渡します。公開側の epoch 更新を確認するか、指定 cycle の待機後にループを再確認します。無効な場合は pause ループとなり、既存の spin 後の条件を満たせば condition variable の sleep に移ります（`engine/src/kernels/cpu/pool.cpp:1088-1116`）。

C02 判定は `umwait_state()` の関数内 `static const` に保存され、最初にその分岐へ到達したときだけ読み取られます。`STRATA_POOL_UMWAIT_ESC` の正値経路、UMWAIT 非対応ビルド、または `STRATA_POOL_UMWAIT` 無効時には C02 の読み取り自体が起きません。初期化後にプロセス環境を変更してもキャッシュ値は更新されません。起動時に別プロセスへ設定を転送する処理は対象名の参照から確認できません（`engine/src/kernels/cpu/pool.cpp:64-66,70-72,1083-1096`）。

## ログと測定値

C02 の値を直接知らせるログ、警告、エラーはありません。`STRATA_POOL_UMWAIT` が正で WAITPKG に対応する CPU では `strata: STRATA_POOL_UMWAIT: parked workers wait with UMWAIT (%lld cycles)`、WAITPKG がない CPU では上記の spin 警告を stderr に出します。後者では C02 は適用されません。非対応ビルドや UMWAIT 無効時はこの関数からログを出しません（`engine/src/kernels/cpu/pool.cpp:45-60`）。C02 による性能測定値は、参照した Strata 資料に条件付きの記載が見当たらないため記載しません。

## 根拠

- `engine/src/kernels/cpu/pool.cpp:40-72` — UMWAIT cycle 値、CPU 判定、C02 の先頭文字判定、エスカレーション値。
- `engine/src/kernels/cpu/pool.cpp:1083-1116` — worker の待機ループと状態値の選択、spin/sleep fallback。
- `engine/cmake/backends/cpu.cmake:241-246` — CPU kernel library への `pool.cpp` の組み込み。
- `engine/src/program/generate.cpp:9001-9008` — 生成経路における `ExpertPool` の構築。
