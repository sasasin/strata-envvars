# `STRATA_EXPERIMENTAL_GFX1150`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。

## 役割

Strata の `setup.py` が、AMD の gfx1150（Radeon 890M / 880M、Strix Point）をサポート対象の GPU として扱うための opt-in です。設定すると、gfx1150 を AMD 対応アーキテクチャ一覧へ追加し、UMA iGPU としてメモリ量を扱います。HIP backend で gfx1150 の GPU を選んだ場合は、setup がそのモデルの実行設定に gfx1150 用の speed switch 群も書き込みます。

これはエンジン実行時に読む変数ではなく、setup の Python プロセスが読む変数です。生成する run config の `env` にこの変数自体を追加する箇所はなく、代わりに対応判定や別の設定値へ反映されます。

## 値と判定

`setup.py` のモジュール初期化時に `os.environ.get(...) == "1"` で文字列全体を比較します。空文字、未設定、`true`、`01`、`1 `、その他すべての値は無効です。数値変換や trim、大文字小文字変換はありません。

| 値 | 判定と結果 |
|---|---|
| 未設定 | opt-in 無効。gfx1150 は `AMD_ARCHS` に含まれず、setup の AMD backend では非対応扱い。 |
| `1` | opt-in 有効。gfx1150 を `AMD_ARCHS` に追加し、UMA として扱う分岐を許可する。 |
| 空文字・`0`・その他 | opt-in 無効。 |

この値を読むのは `setup.py` の import 時です。同じプロセスの途中で環境を書き換えても再評価されません。setup の CLI 引数による上書きはありません。起動時に有効だった場合の結果は、GPU 対応判定や保存される実行設定に反映されます。

根拠: `setup.py:3669-3676`。

## 有効になる条件

- setup が AMD GPU を列挙し、gfx1150 を選ぶ経路で有効です。Linux の KFD 列挙では GPU の arch が `gfx1150` として得られ、Windows では AMD/HIP GPU の列挙結果を使います。いずれも対応判定は `AMD_ARCHS` に基づきます（`setup.py:3783-3787, 4191-4197, 4200-4214`）。
- `--backend hip` を選ぶか、利用可能な NVIDIA GPU がなく AMD 対応 GPU があるため HIP が自動選択される必要があります。gfx1150 だけがあるとき、変数 unset のままでは `amd_problem()` が非対応理由を返し、AMD 使用可能 GPU の一覧に入りません（`setup.py:9361-9374, 9395-9401, 4191-4197`）。
- 変数を `1` にしても HIP エンジンの gfx1150 対応コードが自動で用意されるわけではありません。setup のコメントは Windows に gfx1150 用の ready-made engine がないとし、`STRATA_HIP_ARCHS=gfx1150 tools\hip\build_windows.bat` でビルドして `--prebuilt dist\` を指定する手順を案内しています（`setup.py:3669-3674, 4043-4052`）。
- gfx1150 GPU が実際に選ばれ、backend が HIP の場合に限り、gfx1151 向けに測定されたものを元にした `GFX1150_SWITCHES` が実行設定の `env` に追加されます。gfx1150 以外の GPU、CUDA backend、または opt-in 無効時にはこの追加は行われません（`setup.py:3693-3697, 10303-10327`）。

## 実行時の詳細

opt-in が有効だと `AMD_ARCHS` に `gfx1150` が加わります。この一覧は GPU の受け入れ判定 `amd_problem()`、複数 GPU の選択、および既存のローカル HIP engine の更新時にビルド対象 arch を絞る処理で使われます（`setup.py:3675-3676, 4191-4197, 4217-4221, 5550-5559`）。

また `is_uma_apu()` が gfx1150 を UMA APU と認識し、`amd_apply_uma()` は VRAM を BIOS carve-out として扱い、共有メモリを OS の RAM として扱います。GPU 情報・モデル選択に使う容量が変わり、選択後は Strix Point の説明文を setup の出力に表示します（`setup.py:3824-3847, 4043-4057, 4060-4068, 9445-9452`）。

選んだ GPU が gfx1150 で HIP backend の場合、setup は `GFX1150_SWITCHES`（gfx1103 用 switch 群のコピー）を生成した run config の `env` に加えます。これらは setup 管理キー `SETUP_ENV` に含まれるため、再 setup 時に setup 側で更新されます。対象の GPU/config 条件が合わない場合にこれらの追加はありません（`setup.py:3684-3697, 6498-6509, 10323-10327`）。

直接のログ・失敗経路としては、未対応 GPU の一覧表示に `not supported - Strata's AMD backend runs on ... only, this is gfx1150` が出ます（`setup.py:4191-4197, 9398-9401`）。opt-in 後は GPU 名、容量、arch を表示し、UMA の注意・説明を表示します。値が無効だからという専用の警告や終了処理はありません。ready-made engine や ROCm wheel の取得・ビルドが成功するかは別の setup 処理に依存します。

## 根拠

- 変数の読取、完全一致判定、arch allowlist への追加: `setup.py:3669-3676`。
- gfx1150 の ROCm index 定義: `setup.py:3643-3652`。index はこの変数で読み取られるのではなく、gfx1150 を含む GPU/arch 経路で利用されます。
- UMA 判定、容量計算、非対応判定: `setup.py:3824-3847, 4191-4197`。
- gfx1150 の setup 表示: `setup.py:4043-4057, 4060-4068, 9445-9452`。
- run config の speed switch 追加と setup 管理 env: `setup.py:3684-3697, 6498-6509, 10303-10327`。
- `docs/AMD_HIP.md:42-43` は Strix Point を「setup ではサポートされていない」と説明し、`docs/AMD_HIP.md:537` は setup が gfx1150 用 engine をインストールしないと記載しています。前者は調査対象 commit の `setup.py` にある opt-in 対応と食い違います。後者の ready-made engine がないという説明は、setup のコメント（`setup.py:3671-3674, 4049-4052`）とも一致します。gfx1150 のコミュニティ測定値は `docs/AMD_HIP.md:537, 775` に記載がありますが、本調査では再測定していません。

候補名の全参照を検索した結果、完全一致は `setup.py` の5箇所（コメント/URL記述を含む）で、環境からの実読取は `setup.py:3674` の1箇所でした。外部ライブラリや driver が読む同名変数の挙動は確認・記述対象に含めていません。
