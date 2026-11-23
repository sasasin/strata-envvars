# `GPU_ENABLE_PAL_SDMA`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Strata は、Windows 上で離散 RDNA3 (`gfx1100` / `gfx1101` / `gfx1102`) 向けの arch defaults を適用するとき、この名前がプロセス環境に未設定なら `GPU_ENABLE_PAL_SDMA=1` を設定する。Strata のソースでこの名前の値を機能フラグとして parse する箇所はなく、Strata が確認するのは設定の有無である。既存値があれば値を読み替えず保持する。ここでは Strata が環境変数を追加・保持する動作だけを扱い、外部ライブラリや driver 側の解釈は扱わない（`engine/include/strata/core/gfx11_extra.hpp:41-45,74-80`; `engine/src/core/arch_defaults.cpp:318-324`）。

## 値と判定

`apply_arch_defaults` は環境マップのキー名を使って `std::getenv(kv.first.c_str())` を呼び、戻り値が `nullptr` でなければ既存設定としてスキップする。値の文字列比較・数値変換はしない（`engine/src/core/arch_defaults.cpp:318-324`）。

| 条件 | unset | 設定時に補われる値 | 既存値の扱い |
|---|---|---|---|
| Windows、離散 RDNA3、後述の defaults が有効 | Strata が `1` を設定 | `1` | `getenv` が非 null ならそのまま保持。`0`、`1`、`true`、`false`、空文字列、その他の文字列を Strata は区別しない |
| Windows 以外、対象外 GPU、または defaults 無効 | この名前を追加しない | なし | この名前をこの経路では読み取らず、変更しない |

空文字列は、実行環境で `getenv` が非 null の文字列として返す場合には「設定済み」として扱われる。大文字小文字、前後空白、数値としての妥当性を検査しない。有効値・無効値という値判定はなく、Strata が未設定時に与える値は文字列 `1` だけである（`engine/src/core/arch_defaults.cpp:321-324`）。

## 有効になる条件

- エンジンが HIP build (`STRATA_USE_HIP`) であり、GPU 0 の `cudaGetDeviceProperties` が成功した後に `apply_arch_defaults` が呼ばれること。呼び出しはこの build guard とデバイス情報取得の成功ブロック内にある（`engine/src/program/generate.cpp:4282-4286,4315`）。
- `gcnArchName` が `gfx1100`、`gfx1101`、`gfx1102` のいずれか（任意の `:` feature suffix 付きも含む）で、`integrated` が false であること。対象判定はこの 3 名との完全な名前境界比較であり、`gfx1103`、`gfx1151`、他世代は対象外（`engine/include/strata/kernels/gfx_arch.hpp:15-25`; `engine/include/strata/core/gfx11_extra.hpp:41-45`; `engine/src/core/arch_defaults.cpp:318-320`）。
- OS が Windows であること。この環境変数の組は `windows` が true の場合だけ配列へ追加される。非 Windows では追加されない（`engine/include/strata/core/gfx11_extra.hpp:74-80`; `engine/src/core/arch_defaults.cpp:313-320`）。
- `STRATA_GFX11_DEFAULTS` が先頭文字 `'0'` で始まらず、`STRATA_DEFAULTS` が `026` / `0.2.6` / `v0.2.6` のいずれでもないこと。前者は `off[0] == '0'` で判定し、後者は `qwen_defaults_026()` が完全一致で判定する（`engine/include/strata/core/gfx11_extra.hpp:27-30,41-45`; `engine/include/strata/core/defaults_026.hpp:21-29`）。
- `GPU_ENABLE_PAL_SDMA` 自体が未設定であること。設定済みなら値が `0` でも Strata は上書きしない（`engine/src/core/arch_defaults.cpp:320-324`）。

## 実行時の詳細

環境変数候補の配列は `gfx11_discrete_exact_env` がアーキテクチャ、defaults 無効化条件、Windows 条件から作り、`apply_arch_defaults` が候補ごとに環境を確認する。未設定なら Windows では `_putenv_s(name, value)`、それ以外では `setenv(name, value, 0)` を使うが、この名前は Windows 条件でのみ候補に入るため、実際には Windows の `_putenv_s` 経路で `1` を設定する。設定関数の戻り値はこの箇所で確認していない（`engine/include/strata/core/gfx11_extra.hpp:41-45,74-80`; `engine/src/core/arch_defaults.cpp:218-224,318-324`）。

対象名そのものは static cache されず、`apply_arch_defaults` の実行時に設定有無が確認される。一方、`STRATA_DEFAULTS` は `qwen_defaults_026()` 内の function-local `static const bool` に初回評価結果を保存するため、その初回評価後の変更はこの経路に反映されない（`engine/include/strata/core/defaults_026.hpp:26-29`; `engine/include/strata/core/gfx11_extra.hpp:83-85`; `engine/src/core/arch_defaults.cpp:318-324`）。この呼び出し経路に対象変数を子プロセスへ明示的に転送する処理はない。

CLI 引数による同名設定や上書き順序は見つからない。適用時点で環境に存在する値があればそれが優先され、未設定の場合だけ Strata の既定値が設定される。`STRATA_GFX11_DEFAULTS` / `STRATA_DEFAULTS` は候補配列自体を空にする条件である（`engine/include/strata/core/gfx11_extra.hpp:27-30,41-45,74-80`; `engine/src/core/arch_defaults.cpp:318-324`）。

## ログと測定値

この対象名が新たに設定された場合は `ex11` の一覧に入り、stderr の `strata: gfx11 (RDNA3): ... exact speed switches on by default ...` 行に `GPU_ENABLE_PAL_SDMA` が列挙される。既に設定済みの場合は一覧に入らず、この名前については追加ログが出ない。設定失敗や無効値に対する個別の警告・エラー処理はこの経路にない（`engine/src/core/arch_defaults.cpp:320-332`）。

対象変数に関する Strata 資料上の測定値は確認できなかった。

## 根拠

- `engine/include/strata/core/gfx11_extra.hpp:27-30,41-45,74-85` — gfx11 defaults の無効条件、対象アーキテクチャ、Windows 限定の値追加。
- `engine/include/strata/kernels/gfx_arch.hpp:15-25` — GCN 名の境界判定と対象離散 RDNA3 の列挙。
- `engine/include/strata/core/defaults_026.hpp:21-29` — `STRATA_DEFAULTS` の完全一致判定と初回読み取りの cache。
- `engine/src/core/arch_defaults.cpp:218-224,302-332` — 未設定判定、環境値の設定、stderr ログ。
- `engine/src/program/generate.cpp:4282-4286,4315` — HIP build でデバイス情報取得後に呼び出す経路。
