# `STRATA_EXPERIMENTAL_GFX1150`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

Strix Point の Radeon 890M / 880M（AMD GPU arch `gfx1150`）を、セットアップ時に実験的な HIP 対応 GPU として扱う opt-in です。エンジンが実行中に読む環境変数ではありません。`setup.py` が起動時にこの値を評価し、対応 GPU の許可、統合メモリとしての扱い、および生成する実行設定の内容を切り替えます。

## 値と判定

| 設定 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字 | 無効 |
| 文字列全体が `1` | 有効 |
| その他（例: `0`, `01`, `1x`, `true`） | 無効 |

`os.environ.get("STRATA_EXPERIMENTAL_GFX1150") == "1"` という完全一致です。数値変換や前後空白の除去はありません。結果は `setup.py` のモジュール読み込み時に `GFX1150_OPT_IN` へ保存され、そのセットアッププロセスの間は環境変数を後から変更しても再評価されません。

## 有効になる条件

- セットアップが HIP の AMD GPU 経路を扱うこと。opt-in 時は `gfx1150` が `AMD_ARCHS` に追加され、`amd_problem()` の未対応 arch 判定を通過できます。変数を有効にしても GPU の存在や利用可能性を作り出すものではなく、検出・実行可能性の判定は別途行われます。
- 検出した GPU の arch が `gfx1150` であること。`is_uma_apu()` もこの opt-in と arch の完全一致を条件にするため、対象 GPU は Strix Halo と同様に UMA APU として扱われます。`gfx1152` など他の arch を有効化しません。
- HIP 実行エンジンにも `gfx1150` 向けコードが必要です。ソース上の注記では、Windows の ready-made エンジンに gfx1150 は含まれないため、`STRATA_HIP_ARCHS=gfx1150 tools\hip\build_windows.bat` で作成したエンジンを `--prebuilt dist\` でセットアップに渡す手順を示しています。

opt-in が無効なら `gfx1150` は `AMD_ARCHS` に含まれず、`amd_problem()` はその GPU を未対応として返します。セットアップの GPU 選択、エンジンのアーキテクチャ収録、別の設定や依存ライブラリの可用性まではこの変数だけでは保証されません。

## 実行時の詳細

セットアップは `GFX1150_OPT_IN` が真のときに `gfx1150` を対応 arch リストへ追加します。また `is_uma_apu()` が対象 GPU を UMA と判定するため、GPU のメモリ情報は専用領域と共有メモリを合わせて扱う `amd_apply_uma()` の経路に入ります。

選択された GPU が HIP backend かつ arch `gfx1150` なら、作成するモデル設定の `env` に `GFX1150_SWITCHES` を追加します。この辞書は `GFX1103_SWITCHES` のコピーで、`STRATA_GDN_HEAD`, `STRATA_GDN_PP`, `STRATA_GDN_CONVL2`, `STRATA_GDN_NOY`, `STRATA_CVEC_FUSE`, `STRATA_PF_PAD`, `STRATA_Q8_PACKED`, `STRATA_Q6_PACKED`, `STRATA_MMVF_ROWS`, `STRATA_ATTN_LANECELL`, `STRATA_EXPERT_V2`, `STRATA_TSUM`, `STRATA_LFUSE`, `STRATA_GDN_SPLIT`, `STRATA_QFUSE`, `STRATA_PLE_BATCH`, `STRATA_SH_STREAM` を設定します。セットアップ側の注記では gfx1150 のエンジン arch defaults にこれらの設定がないため、設定ファイル経由で与えるとしています。ここで設定されるのはこれらの別環境変数であり、`STRATA_EXPERIMENTAL_GFX1150` 自体をエンジンへ渡す処理ではありません。

これらの `env` 項目は `SETUP_ENV` に含まれるセットアップ管理項目です。既存設定を再生成するときはセットアップが更新し、opt-in を外して再実行した場合は以前の gfx1150 用項目を引き継がないよう `carry_over()` が除外します。セットアップの説明文は、GPU を opt-in した場合に gfx1150/UMA 向けの案内を出す経路にも使われます。

## 文書との照合

この HEAD の `setup.py` には gfx1150 を opt-in で対応 arch に追加し、HIP のモデル設定を作る実装があります。一方、同じ checkout の `docs/AMD_HIP.md:71,620-628` は「Strix Halo 以外の統合 Radeon は非対応」「setup does not install for it yet」と説明しています。現行ソースと文書の記述は一致しないため、セットアップの現状についてはこの調査対象 commit の実装を根拠とし、文書側の説明は古い状態として扱います。

## 根拠

- `setup.py:2125-2132`: 対象 GPU と実験的 opt-in の説明、完全一致判定、`AMD_ARCHS` への追加。
- `setup.py:2140-2153`: gfx1150 用設定辞書とその由来。
- `setup.py:2259-2265,2275-2280`: UMA APU 判定とメモリ情報への適用。
- `setup.py:2570-2575`: 未対応 arch の拒否条件。
- `setup.py:2435-2449,2452-2459`: gfx1150 向けセットアップ案内。
- `setup.py:4521-4529,4534-4549,7020-7040`: 設定への env 追加と、セットアップ再実行時の管理。
- `docs/AMD_HIP.md:71,620-628`: 現行ソースと食い違う説明。
