# `--backend`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点、`main` / `origin/main` と一致、未コミット変更なし）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-terminal` |
| コマンド | `strata update` |
| オプション | `--backend` |
| 別名 | なし |
| 値 | 文字列を 1 つ取る（エンジン family 名、GPU メーカー名、または `hip-<variant>`） |

## 役割

この PC の GPU 検出結果の代わりに、更新で入れるエンジンの family を指定する。検出と違う family を選びたい PC（NVIDIA と AMD の両方がある、Intel カードを使う、variant まで決めたい）で、取得・テスト起動・切り替えの対象を固定するために使う。

## 使い方

```bash
# 変更せずに、AMD(hip) 向けにどのパッケージが選ばれるかだけを見る
strata update --check --backend amd

# Intel(sycl) のエンジンを取得して切り替える
strata update --backend intel

# AMD の rdna2 ビルドを名指しする
strata update --backend hip-rdna2
```

## 値と既定値

- 未指定（`--backend` を渡さない、または空文字）なら検出経路に戻る（`terminal/strata_cli/update_cmd.py:316`）。
- 小文字化と前後空白の除去だけを行う（`terminal/strata_control/engine_component.py:491`）。`argparse` に `choices` は無く、値の検証はパーサでは行わない（`terminal/strata_cli/update_cmd.py:50`）。
- 受理される名前（`terminal/strata_control/engine_component.py:490`、`terminal/strata_control/targets.py:25`）:
  - family 名: `cuda` / `hip` / `sycl` / `metal` / `cpu`
  - GPU メーカー名の別名: `nvidia`→`cuda`、`amd`→`hip`、`intel`/`arc`→`sycl`（`terminal/strata_control/engine_component.py:502`）
  - `hip-<variant>`（例 `hip-rdna2`）: family は `hip`、variant は後半（`terminal/strata_control/engine_component.py:495`）
- 上記以外の語もエラーにならず、その語がそのまま family として扱われる（`terminal/strata_cli/update_cmd.py:294`）。結果は後述のとおり「この PC 向けは無い」になる。
- 既定値は `None`。この指定は保存されないので、次回の `strata update` は再び検出（または `strata launch --backend` が保存した選択、`terminal/strata_control/engine_component.py:551`）に従う。

## 実行時の動作

1. `run()` が `--backend` の有無で分岐し（`terminal/strata_cli/update_cmd.py:316`）、指定時は `requested_hardware()`（同 `:283`）を呼ぶ。
2. family が `BACKEND_MATRIX` にある語なら、`STRATA_ENGINE_BACKEND` に family を入れた環境で `updater.detect_hardware()` を呼び、**その family のカードの情報**（hip なら gfx 名、cuda ならドライバと arch）を読み直す（同 `:292`）。未知の語なら通常の検出結果の `backend` だけをその語で上書きする（同 `:294`）。`hip-<variant>` の variant は `variant_wanted` に入る（同 `:297`）。
3. `backend_source` は常に `"requested"` になり（同 `:299`）、「別メーカーのエンジンへ乗り換えない」ガード（`terminal/strata_control/updater.py:654`、同 `:1501`）を本人の決定として通す。
4. パッケージ選択は `select_engine()`。プラットフォーム一致の後、`pkg.backend` が指定 family と一致することを要求する（`terminal/strata_control/feed.py:739`）。variant 指定時は一致する variant があれば絞り込み、無ければ絞り込まない（同 `:773`）。gfx 不明で複数の hip variant が適合した場合は、指定 variant、GPU 名、導入済み variant の順に決め、決められなければ理由を付けて hip を除外する（同 `:796`）。
5. `installed_before` も同じ family で解決され（`terminal/strata_control/updater.py:610`）、切り替え後もその family で選ばれるエンジンかを確認する（同 `:1587`）。
6. Control と app は `hardware["platform"]` しか使わないため影響を受けない（`terminal/strata_control/updater.py:1921`、同 `:2004`）。モデル形状ごとのエンジンは同じ `ctx.hardware` を共有するため影響を受ける（`terminal/strata_control/shape_engine.py:301`）。`--no-engine` を併用するとエンジンとモデル形状の手順自体が省かれ、`--backend` は何も変えない（`terminal/strata_control/updater.py:2097`）。

## 適用条件と副作用

- 取得するのは指定 family のパッケージで、既存の別 family のエンジンは削除されず残る（`terminal/strata_control/updater.py:1615`）。
- テスト起動は取得したパッケージ自身の backend を使う（`terminal/strata_control/updater.py:1372`）。`--backend` がテスト起動の引数として転送されるわけではない。
- 対応する OS/arch は family ごとに固定（`terminal/strata_control/targets.py:25`。`sycl` は Linux x86_64 のみ、`metal` は macOS arm64 のみ）。合わない組み合わせは取得を試みず「この PC 向けは無い」になる。
- 指定 family のカードが実機に無い場合（例 NVIDIA のみの PC で `--backend hip`）は gfx が読めず variant を決められないことがある。その場合は理由付きで `none-for-this-pc` になる（`terminal/strata_control/feed.py:808`）。メーカーガードで拒否されることはない。
- `strata components update` も同じパーサ定義を共有する（`terminal/strata_cli/update_cmd.py:70`）。本稿は `strata update` の文脈のみを扱う。

## 出力とエラー

- パッケージが無い／未知の語のとき、`strata update` はエンジンについて `none-for-this-pc` の注記を出して**そのまま続行し、終了コード 0** になる（`terminal/strata_control/updater.py:1489`）。Control などの他ステップは実行される。
- `--check` では `Engine` 行の下に選ばれたパッケージと除外理由の一覧が出る（`terminal/strata_cli/update_cmd.py:229`）。`--output json` / `jsonl` では hardware（`backend` など）が含まれる（`terminal/strata_control/updater.py:775`）。
- 未知の語でも usage エラー（終了コード 2）にはならない。`strata launch --backend` が未知の語を終了コード 2 で拒否するのとは挙動が異なる（`terminal/strata_cli/launch/cmd.py:831`）。
- 署名・ハッシュ・ダウングレード拒否など既存の失敗経路（終了コード 5・6）は `--backend` で変わらない（`terminal/strata_cli/update_cmd.py:379`）。

## 根拠

- `terminal/strata_cli/update_cmd.py:50` — `--backend` の parser 定義（`default=None`、検証なし）。
- `terminal/strata_cli/update_cmd.py:283`–`:300` — 指定 family のハードウェア読み直し、variant、`backend_source="requested"`。
- `terminal/strata_cli/update_cmd.py:316` — 指定時と検出時の分岐。
- `terminal/strata_control/engine_component.py:490`–`:502` — 名前の正規化と別名、`hip-<variant>` の分解。
- `terminal/strata_control/feed.py:739`、`:773`、`:796` — backend 一致、variant 絞り込み、variant を決められない場合。
- `terminal/strata_control/updater.py:654`、`:1501` — メーカーガードが `requested` を通す箇所。
- `terminal/strata_control/updater.py:1489`、`:1587`、`:1615` — パッケージ無しの継続、切り替え後の確認、旧エンジン保持。
- 補助資料: 同一 revision の `python3 strata.py update --help`（`--backend BACKEND  choose an engine family instead of detecting this PC's GPU`）は parser 定義と一致。ユーザー向け `docs/` に `strata update --backend` の記載は無い（`docs/INTEL_ARC.md:25` は `strata launch --backend` の保存選択が `strata update` にも効くと述べるのみ）。
