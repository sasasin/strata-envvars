# `STRATA_KFD_QUIET_XFER`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

Linux の HIP ビルドで、KFD topology 上の全 GPU node が gfx1103 / gfx1150 / gfx1151 のいずれかである場合、Strata は HIP の初期化前に `GPU_PINNED_MIN_XFER_SIZE=1000000` をプロセス環境へ追加します。この変数はその自動設定を止める個別スイッチです。設定自体を行うのは `src/program/generate.cpp` の `main` で、対象名を `fix_env(Fix::Xfer)` が返し、`switch_on` が値を判定します（`src/program/generate.cpp:3591-3603`、`include/strata/core/kfd_quiet.hpp:47-65`）。

Strata のコード上で確認できる直接の効果は、既定値を `setenv` で設定することです。カーネルや計算内容を変更する処理ではありません。コードコメントは、この設定を pageable copy の staging 経路を選ばせる意図として説明していますが、runtime 側の動作はこの文書の調査範囲外です（`include/strata/core/kfd_quiet.hpp:11-12`、`src/program/generate.cpp:3592-3600`）。

## 値と判定

対象変数は `STRATA_KFD_QUIET` とともに `switch_on(all, one)` に渡されます。いずれかが設定済みで先頭文字が `0` なら無効、そうでなければ有効です。文字列全体の解析、数値変換、大文字小文字変換、空白除去はありません（`include/strata/core/kfd_quiet.hpp:47-52`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Linux + `STRATA_USE_HIP`、対象 topology、かつ `GPU_PINNED_MIN_XFER_SIZE` が未設定 | 有効 | `1`、`true`、`false`、空文字、` 0` など（先頭文字が `0` 以外） | `0`、`0anything` など（先頭文字が `0`） |

明示的な空文字は「設定済み」ですが、空文字の先頭文字は `0` ではないためこのスイッチを無効にしません。`STRATA_KFD_QUIET=0` または `STRATA_KFD_QUIET_XFER=0` のどちらかが優先して無効化します。個別変数が `1` でも全体変数の先頭文字が `0` なら有効になりません。これらは `xfer_value` で同じ判定結果になります（`include/strata/core/kfd_quiet.hpp:47-52,251-257`）。

## 有効になる条件

- 実行ファイルが `STRATA_USE_HIP` と `__linux__` の両方でビルドされていること。`STRATA_HIP_GFX906` だけではこの処理に入りません（`src/program/generate.cpp:3591-3592`）。
- `/sys/class/kfd/kfd/topology/nodes` を読み、少なくとも一つの GPU node（`simd_count > 0`）があり、すべての GPU node の `gfx_target_version` が `110003`、`110500`、`110501` のいずれかであること。混在 GPU 構成は対象外です（`src/program/generate.cpp:3597-3599`、`include/strata/core/kfd_quiet.hpp:172-195,198-212,228-247`）。
- `STRATA_KFD_QUIET` と `STRATA_KFD_QUIET_XFER` のいずれも先頭文字が `0` でないこと（`include/strata/core/kfd_quiet.hpp:47-52,254-256`）。
- `GPU_PINNED_MIN_XFER_SIZE` が未設定であること。空文字を含め、既に設定されていればその値を残します（`src/program/generate.cpp:3598-3600`、`include/strata/core/kfd_quiet.hpp:251-256`）。

CLI 引数による上書き経路はありません。`STRATA_ARENA_MMAP` が先に `GPU_PINNED_MIN_XFER_SIZE` を設定する場合があります。HIP または `STRATA_HIP_GFX906` の非 Windows ビルドで同変数の先頭文字が `1` なら `setenv(..., 0)` を呼ぶため、その後の XFER 処理は既存値として扱い、上書きしません（`src/program/generate.cpp:3582-3590,3598-3600`）。

## 実行時の詳細

`main` の冒頭にある `--version`、`--families`、`--geometry` の早期終了より後、HIP 初期化より前に一度 topology を読み、環境変数を評価します（`src/program/generate.cpp:3560-3581,3591-3600`）。topology の各 `properties` ファイルから `gfx_target_version` と `simd_count` の数値部分を読み、SIMD 数が正の node だけを GPU として数えます（`include/strata/core/kfd_quiet.hpp:172-195,198-212,228-247`）。

topology ディレクトリを開けない場合は空の node 一覧となり、対象クラス判定は偽です。個別の `properties` を開けない node は追加されず、読み取り失敗を示すエラー処理や fallback 設定はありません（`include/strata/core/kfd_quiet.hpp:228-247`）。対象条件が成立すると、`setenv("GPU_PINNED_MIN_XFER_SIZE", "1000000", 0)` を呼びます。最後の `0` により既存値を上書きしません。判定は起動時に一度だけで、後から環境を変更してもこの分岐は再評価されません（`src/program/generate.cpp:3596-3603`）。

`setenv` の戻り値は確認されず、失敗時の専用エラーや fallback はありません。`STRATA_TRACE` が設定済み（空文字を含む）なら、`setenv` 呼び出し後に次の行を stderr に出します。戻り値を検査しないため、このログだけでは設定成功を保証しません（`src/program/generate.cpp:3600-3602`）。

## ログと測定値

設定を試み、かつ `STRATA_TRACE` が設定されている場合の stderr 出力は次のとおりです。

```text
strata trace: kfd quiet: GPU_PINNED_MIN_XFER_SIZE=1000000 (pageable copies staged by the runtime)
```

対象外の build / topology、どちらかの quiet スイッチが先頭文字 `0`、または `GPU_PINNED_MIN_XFER_SIZE` が既に設定済みの場合、この XFER 処理からは出力しません。対象変数自体に関する Strata 資料の測定値は確認できませんでした（`src/program/generate.cpp:3591-3603`）。

## 根拠

- 対象 build 条件、topology 判定、既存値を保持した環境変数設定と trace: `src/program/generate.cpp:3591-3603`
- switch の先頭文字判定と個別環境変数名の対応: `include/strata/core/kfd_quiet.hpp:47-65`
- topology の node 読み取り・対象 GPU class 判定: `include/strata/core/kfd_quiet.hpp:172-195,198-212,228-257`
- 早期終了と XFER 設定処理の位置関係: `src/program/generate.cpp:3560-3581`
- `STRATA_ARENA_MMAP` による先行設定: `src/program/generate.cpp:3582-3590`
