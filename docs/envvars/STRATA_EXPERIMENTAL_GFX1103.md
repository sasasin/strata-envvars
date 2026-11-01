# `STRATA_EXPERIMENTAL_GFX1103`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

この変数は Strata engine の実行時設定ではなく、`setup.py` の AMD GPU セットアップに対する gfx1103（Radeon 780M / 760M / 740M、Ryzen 7040 / 8040）の opt-in です。セットアップが gfx1103 を対応 AMD arch として扱い、Linux の gfx1103 HIP 構成には専用の環境設定を run config に書きます。コードコメントはこのサポートを experimental / unsupported と位置づけています（`setup.py:3665-3668`）。

候補名の全参照を検索した結果、値を実際に読むのは `setup.py:3668` のみです。C++/CUDA/HIP/SYCL engine や `serve` に、この名前を読んで処理を分岐するコードはありません。通常の engine 実行時にこの変数自体を設定しても、engine の挙動を切り替える処理は確認できません。

## 値と判定

`os.environ.get("STRATA_EXPERIMENTAL_GFX1103") == "1"` で文字列全体を比較します。数値変換、trim、大文字小文字変換はありません。

| 環境の値 | opt-in |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| `1` | 有効 |
| `0`、`true`、`01`、`1 `、` 1` など、文字列全体が `1` でない値 | 無効 |

判定値 `GFX1103_OPT_IN` は `setup.py` の import 時に一度設定されます。setup プロセスの起動後に環境を書き換えても再評価されず、次の setup 起動で読み直されます（`setup.py:3668`）。この変数に対応する CLI 引数や、CLI が値を上書きする分岐はありません。

## 有効になる条件

- **セットアップでの GPU 対応判定:** `GFX1103_OPT_IN` が真なら `AMD_ARCHS` に `gfx1103` を加えます。GPU 列挙で検出した arch がこの一覧にあるかを `amd_problem()` が確認するため、opt-in なしでは gfx1103 は未対応とされ、opt-in 時には他のチェックを通れば使用可能になります（`setup.py:3675-3676, 4142-4187, 4191-4197`）。
- **AMD APU としてのメモリ扱い:** gfx1103 を UMA APU と判定し、BIOS carve-out と shared memory を使って setup の GPU memory 情報を作ります。これは対応 arch に加える opt-in と同じ判定値に依存します（`setup.py:3824-3847`）。
- **HIP backend:** gfx1103 向けの table 探索と追加設定は HIP の config 生成経路にあります。HIP を選ばない構成ではこの設定生成分岐に入りません（`setup.py:10305-10323`）。
- **OS:** `STRATA_NO_ARENA_THP=1` と17個の gfx1103 speed switch を config の `env` に加える分岐は `not WIN` の場合だけです。Windows では opt-in 判定自体は arch 対応・UMA 判定に使われますが、この2種類の設定は生成されません（`setup.py:10316-10322`）。`docs/RADEON_780M.md:1-5` は gfx1103 の手順を Linux 向けとし、ready-made Windows engine はないと説明しています。
- **既存設定との関係:** 再セットアップ時、gfx1103 switch 群と `STRATA_NO_ARENA_THP` は setup 管理値として古い config から引き継がれません。今回の条件で新しい config に設定された値が使われ、opt-in を外した場合に古い setup 値が残り続けない処理です（`setup.py:6502-6509, 6525-6530`）。

## 実行時の詳細

Linux で HIP backend の config を作る場合、選択 GPU が gfx1103 で opt-in が有効なら、setup は `STRATA_NO_ARENA_THP=1` と `GFX1103_SWITCHES` の17項目を `cfg["env"]` に記録します。switch 群は `STRATA_GDN_HEAD=1`, `STRATA_GDN_PP=2`, `STRATA_GDN_CONVL2=1`, `STRATA_GDN_NOY=1`, `STRATA_CVEC_FUSE=1`, `STRATA_PF_PAD=1`, `STRATA_Q8_PACKED=1`, `STRATA_Q6_PACKED=1`, `STRATA_MMVF_ROWS=1`, `STRATA_ATTN_LANECELL=1`, `STRATA_EXPERT_V2=1`, `STRATA_TSUM=1`, `STRATA_LFUSE=1`, `STRATA_GDN_SPLIT=1`, `STRATA_QFUSE=1`, `STRATA_PLE_BATCH=1`, `STRATA_SH_STREAM=1` です（`setup.py:3684-3692, 10316-10322`）。setup は生成した config を保存します（`setup.py:6648-6676, 10436-10453`）。

保存済み calibration が適用される場合、calibration の `env` は `STRATA_SH_STREAM` を再設定できるため、この17項目のうち同名の値は calibration 値が優先します。他の env 項目は `apply_env()` の `ENV_KEYS` に含まれないため、この処理では変更されません（`tools/calibrate.py:514-522`, `setup.py:10437-10444`）。

同じ HIP 経路では選択 GPU の arch と hipBLASLt version に合う table が見つかれば `STRATA_HIPBLASLT_TUNING` も config に設定します。gfx1103 用 table が見つからない場合、setup の `hipblaslt_table()` は warning を出し、table なしを返します。table は opt-in の文字列を別途読むものではなく、HIP config 経路と arch/version によって選択されます（`setup.py:4760-4781, 10313-10315`）。ROCm の wheel を使う場合、gfx1103 は `gfx110X-all` index を選び、専用 pin は `7.10.0a20251121` です。ただし `STRATA_ROCM_INDEX` と `STRATA_ROCM_VERSION` が別途設定されれば index / version 選択に使われます（`setup.py:3652-3663, 3716-3717, 4707-4727`）。これらは gfx1103 opt-in 判定そのものを変更しません。

server は config の `env` を engine 子プロセス環境へ反映します。同名の親プロセス環境値より config 値が後から設定されます（`serve/server.py:3747-3764`）。したがって Strata が runtime に適用するのは setup が書いた各設定値です。`STRATA_EXPERIMENTAL_GFX1103` 自体は config に書かれず、engine のコードも読まないため、起動後のログや処理にこの opt-in 名固有の分岐・警告・終了経路はありません。

setup の GPU 表示では、対応外なら `amd_problem()` の `not supported ... this is gfx1103 (an integrated Radeon, not Strix Halo)` が理由として表示され、対応扱いなら `can be used` と表示されます（`setup.py:4191-4197, 9400-9407`）。値が `1` 以外だったことだけを示す専用 warning/error は見つかりません。`--check` を含む setup は GPU の検出結果をこの判定で表示します（`setup.py:9360-9364, 9400-9407`）。

## 根拠

- 候補一覧: `docs/envvars/000_envvers.md:775`。
- 値の唯一の実読み取り、arch list と ROCm family pin: `setup.py:3652-3676`。
- Linux KFD GPU 列挙、arch 判定、UMA 判定とメモリ分類: `setup.py:3824-3847, 4142-4197`。
- gfx1103 switch 群と setup config 生成、HIP 条件・Windows 除外: `setup.py:3684-3692, 6498-6509, 10303-10323`。
- hipBLASLt table の選択と未発見時の warning: `setup.py:4760-4781, 10313-10315`。
- 保存済み config の `env` を子プロセスへ反映: `setup.py:6648-6676`, `serve/server.py:3747-3764`。
- 関連説明（設計資料）: `docs/RADEON_780M.md:1-5, 66-80`; 測定条件や性能値はこの調査で再測定していません。
