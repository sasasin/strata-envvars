# `STRATA_EXPERIMENTAL_GFX1150`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

`terminal/setup.py` が、AMD Radeon 890M / 880M（gfx1150）をセットアップで使える AMD GPU アーキテクチャとして扱うかを制御します。変数はエンジンが読む実行時設定ではありません。セットアップ時に `AMD_ARCHS` へ gfx1150 を追加し、その後の対応 GPU 判定、HIP 用 ROCm の選択、および選択 GPU 用エンジンのビルド経路へ影響します（`terminal/setup.py:4415-4422`, `4950-4956`, `5572-5617`）。

既定値は有効です。変数名やコメントに「experimental」「opt-in」とありますが、実装は未設定時に gfx1150 を有効にし、明示的な文字列 `0` だけで無効にします（`terminal/setup.py:4415-4417`）。

## 値と判定

`os.environ.get("STRATA_EXPERIMENTAL_GFX1150", "1") != "0"` の文字列完全一致で判定し、結果をモジュール読み込み時に `GFX1150_OPT_IN` へ保存します。数値変換や真偽値パーサーは使いません（`terminal/setup.py:4415-4417`）。

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `terminal/setup.py` の読み込み時 | 既定文字列 `"1"` なので有効 | 空文字、`1`、`true`、`false`、`00`、`0 ` など、値が文字列 `"0"` と一致しないもの | `0` のみ |

大文字小文字や空白を正規化しません。したがって `false` や ` 0` は無効化値ではなく有効側です。範囲・数値妥当性・境界値の検証もありません。CLI 引数がこの値を上書きする経路はなく、`--backend` は AMD 経路を選ぶ指定ですが gfx1150 の対応判定自体はこの環境値で決まります（`terminal/setup.py:4415-4422`, `11380-11383`, `11560-11575`）。

## 有効になる条件

- gfx1150 GPU が検出され、セットアップが AMD GPU 判定を行う必要があります。無効時もデバイス自体の検出・アーキテクチャ名判定は行いますが、gfx1150 は `AMD_ARCHS` に含まれないため `amd_problem()` が未対応として返します（`terminal/setup.py:4533-4537`, `4950-4956`）。
- 有効時、gfx1150 は `AMD_ARCHS` に入ります。Linux では AMD backend を選ぶ必要があり、`--backend hip` で明示するか、利用可能な NVIDIA GPU がなく利用可能な AMD GPU があるときに自動選択されます。利用可能な NVIDIA GPU がある場合、backend の自動選択は NVIDIA と AMD の選択肢を出します（`terminal/setup.py:11560-11592`）。
- Linux の HIP エンジン構築では選択アーキテクチャが `build_engine_hip()` に渡り、gfx1150 を含む `CMAKE_HIP_ARCHITECTURES` を指定します。十分なシステム ROCm が使えない場合、gfx1150 用 TheRock wheel index を使う経路もあります（`terminal/setup.py:4389-4399`, `4466-4467`, `5473-5516`, `5572-5617`）。この環境変数自体は ROCm のバージョンや index を選びません。周辺では `ROCM_PATH` がシステム ROCm の場所、`STRATA_ROCM_INDEX` が wheel index、`STRATA_ROCM_VERSION` が wheel の版を指定します（`terminal/setup.py:4409-4411`, `4466-4467`, `5478-5495`, `5503-5509`）。
- Windows でも対応アーキテクチャ判定への追加は同じですが、セットアップの AMD engine 経路は ready-made HIP engine を取得し、その build metadata に gfx1150 が含まれるかを別途確認します。利用できるエンジンがなければセットアップは停止します。この変数だけでは Windows のエンジンを用意しません（`terminal/setup.py:5366-5383`, `5417-5435`, `9522-9528`）。
- 有効時は gfx1150 の APU として UMA 判定やセットアップの説明文を適用します。無効時は Strix Halo 用の特例を除き、gfx1150 をこの APU 経路に通しません（`terminal/setup.py:4574-4586`, `4596-4603`, `4819-4827`）。
- ビルド macro、サーバーモード、モデル状態による追加判定はありません。起動済みモデルの実行時にこの変数を読むエンジン側の箇所も見つかりません。

## 実行時の詳細

この環境変数名の全参照では、実際の値読み取りは `terminal/setup.py:4417` の一箇所です。その他の参照はコメント上の記載です。値は Python が `terminal/setup.py` を読み込む時点で一度評価され、`GFX1150_OPT_IN` と `AMD_ARCHS` に保持されます。そのプロセスで後から環境値を書き換えても、すでに作られた対応アーキテクチャ一覧は再計算されません（`terminal/setup.py:4415-4422`）。

無効時に gfx1150 を HIP backend で使おうとすると、GPU 一覧では `not supported - Strata's AMD backend runs on ... only, this is gfx1150 (an integrated Radeon, not Strix Halo)` として扱われ、利用可能な AMD GPU がなければ `no AMD GPU Strata can use` で失敗します（`terminal/setup.py:4950-4956`, `11597-11618`）。有効時も、GPU 選択、OS、HIP/ROCm の利用可否や Windows の ready-made engine の対応状況によっては、gfx1150 での導入・ビルドに至らないことがあります。

この変数を Strata が run config の `env` に書き込む処理は確認できません。setup が生成する設定には gfx1150 用 speed switches が別途ありますが、この変数自体とは別物です（`terminal/setup.py:4439-4443`, `7460-7463`）。

## ログと測定値

この変数を読み取ったことや値を有効化したことだけを示す専用ログはありません。無効時の未対応理由と AMD GPU 不在時の失敗は上記のとおりです（`terminal/setup.py:4950-4956`, `11597-11618`）。有効時は通常の GPU 検出・選択ログに反映されます。

Strata 内の `docs/AMD_HIP.md` は gfx1150 を「setup で未対応」と記しています（`docs/AMD_HIP.md:42-43`）。また同文書は gfx1150 について「Setup does not install for it」としています（`docs/AMD_HIP.md:565`）。これは今回調査した commit の `terminal/setup.py` の実装、すなわち未設定を有効扱いして gfx1150 を `AMD_ARCHS` に含める挙動と整合しません。文書側の更新時期や未反映理由はソースから確認できません。ベンチマーク資料の数値はこの環境変数の効果としては扱いません。

## 根拠

- 値の読み取り、既定値、gfx1150 の対応一覧への追加: `terminal/setup.py:4415-4422`
- gfx1150 の ROCm index と system/wheel 選択: `terminal/setup.py:4389-4399`, `4409-4411`, `4466-4467`, `5473-5516`
- GPU 対応判定と未対応理由: `terminal/setup.py:4950-4956`
- Linux の backend 選択と未対応時の失敗: `terminal/setup.py:11560-11618`
- Linux HIP engine の build 対象アーキテクチャ: `terminal/setup.py:5572-5617`
- Windows ready-made engine の条件: `terminal/setup.py:5366-5383`, `5417-5435`, `9522-9528`
- UMA 判定とセットアップ案内: `terminal/setup.py:4574-4586`, `4596-4603`, `4819-4827`
- Strata docs との不整合: `docs/AMD_HIP.md:42-43`, `565`
