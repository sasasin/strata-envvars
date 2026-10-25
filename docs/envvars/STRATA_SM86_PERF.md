# `STRATA_SM86_PERF`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。

## 役割

CUDA 起動時に compute capability 8.6（sm_86）向けの既定パフォーマンススイッチ群を適用するかを制御します。値が `0` で始まる場合は、この既定群を適用しません。個々のスイッチを利用者が設定している場合は、この変数で既定群を有効にしても、その利用者設定が優先されます。

## 値と判定

| 値 | sm_86 での扱い |
|---|---|
| 未設定 | 既定スイッチ群を適用 |
| 空文字 | 既定スイッチ群を適用。設定済みの変数としては扱われないため、個別スイッチの既定値は注入される |
| 先頭文字が `0`（例: `0`, `0abc`） | 既定スイッチ群を適用しない |
| その他（例: `1`, `true`, `false`, ` 0`） | 既定スイッチ群を適用 |

判定は `getenv()` の戻り値が非 null かつ `v[0] == '0'` かどうかだけです。数値変換、文字列全体の比較、大文字小文字変換はありません。したがって `false` は無効化値ではなく、空白の後に `0` がある値も無効化値ではありません。sm_86 以外ではこの変数を判定する分岐に入りません。根拠: `src/core/nv_defaults.cpp:11-23`。

## 有効になる条件

- CUDA ビルドで、実行時に見える全 GPU が同じ compute capability であること。1台でも異なる capability の GPU がある場合、または GPU 数・属性の取得に失敗した場合、起動コードは既定群の適用を呼びません。
- 共通 capability が 8.6 であること。`STRATA_EMULATE_CC` が有効なら capability 判定はエミュレート値を使うため、物理 GPU が sm_86 でなくても sm_86 の既定群が選ばれることがあります。
- 起動時の初期化経路まで到達すること。HIP と Metal のビルドではこの CUDA 専用の呼び出しがコンパイル対象外です。

根拠: `src/program/generate.cpp:2800-2817`, `src/core/nv_defaults.cpp:18-23`, `include/strata/core/emulate.hpp:14-24`。

## 実行時の詳細

コマンドライン引数の解析後、エンジンが個々のスイッチを読む前に、Strata は GPU 数と各 GPU の compute capability を調べます。すべて同じであれば `apply_nv_defaults()` を呼びます。sm_86 かつ `STRATA_SM86_PERF` の先頭文字が `0` でなければ、次の環境変数を既定値として設定します。

| 環境変数 | 注入値 |
|---|---:|
| `STRATA_ADAPT_NOWAIT` | `1` |
| `STRATA_ADAPT_LAG` | `2` |
| `STRATA_CPU_IQ_ALL_EXACT1` | `1` |
| `STRATA_SIDE_MIXER` | `2` |
| `STRATA_ATTN_DAILY` | `1` |
| `STRATA_GR_UP75` | `1` |
| `STRATA_GU_SWIGLU` | `1` |
| `STRATA_QSA_ROWS` | `1` |
| `STRATA_B6_MMVQ_ROWS` | `1` |

注入には `setenv(..., 0)`（Windows は `_putenv_s`）を使います。各スイッチ名が既に環境に存在すれば、値が `0` や空文字でも上書きしません。1つ以上を注入した場合、stderr に `strata: sm_86 (Ampere): ... exact speed switches on by default (STRATA_SM86_PERF=0 turns them off; a switch you set is kept): ...` という形式の行を出し、注入した変数名を列挙します。変数が `0` で始まる場合や、既定群の適用対象でない場合はこのログを出しません。根拠: `src/core/nv_defaults.cpp:52-70`。

この判定と注入は `generate` 起動時の一度だけです。起動後に親プロセスの環境を書き換えても、すでに注入された設定は再評価されません。起動ラッパーによる子プロセスへの環境転送・変更は、この処理からは確認できません。

## 資料との照合

`docs/DETAILS.md:2425-2453` は sm_86 の既定スイッチ一覧、`STRATA_SM86_PERF=0` による抑止、RTX 3060 / RTX A4000 での測定値を記載しています。そこに記された条件は IQ3_XXS、既定フラグ、fresh engine、8 組の interleaved pairs などです。測定値は同資料の条件下の報告であり、この環境変数自体の単独効果を示す値ではありません。実装では sm_86 テーブルを空にすることで既定群全体を抑止します。

## 根拠

- `include/strata/core/nv_defaults.hpp:1-13`: スイッチ群の対象、抑止値、利用者設定の優先、起動時適用の説明。
- `src/core/nv_defaults.cpp:11-49`: 環境変数の値判定と sm_86 スイッチ群。
- `src/core/nv_defaults.cpp:52-70`: 既存値を保った環境への注入と stderr ログ。
- `src/program/generate.cpp:2800-2817`: CUDA 起動時の GPU 一覧確認と適用呼び出し。
- `include/strata/core/emulate.hpp:14-24`: compute capability のエミュレーション。
- `docs/DETAILS.md:2425-2453`: 設計資料と測定条件。
