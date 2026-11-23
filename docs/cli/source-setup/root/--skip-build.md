# `setup.py --skip-build`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `source-setup` |
| コマンド | `setup.py` / `setup.sh` / `START-HERE.bat`（セットアップのルート） |
| オプション | `--skip-build` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

現行 parser は `--skip-build` を受理しますが、値を参照する処理がなく、エンジンのビルドを抑止しません。ビルドを選ぶ既知のフラグは `--build` で、通常のエンジン選択では `a.build` により既製エンジンを使わずビルド経路へ進みます。したがって `--skip-build` にビルド回避の効果を期待できません。

## 使い方

```sh
# parser は受理するが、ビルド選択への効果はない
./setup.sh --skip-build
```

## 値と既定値

値を取らない `argparse` の `store_true` フラグです。指定時は parser の属性 `a.skip_build` が真になり、省略時は既定値の偽です。明示的な値は受け付けず、同じフラグを複数回指定しても真のままです。ヘルプ表示は `argparse.SUPPRESS` により抑制されています（`terminal/setup.py:11384-11385`）。

## 実行時の動作

この checkout の `terminal/setup.py` 内では `skip_build` / `skip-build` の出現は parser 宣言のみです。`a.skip_build` を読む箇所や、その値を別処理へ渡す箇所は確認できませんでした。通常のエンジン選択は `a.build` によって既製エンジン取得を飛ばし、エンジンをビルドするか決めています（`terminal/setup.py:9513-9542`）。また、`--update --build` では `a.build` が再ビルド指定として転送されます（`terminal/setup.py:8413-8427`）。

Intel SYCL 経路では `setup.py` が生の引数列を `sycl_setup` に渡し、同関数は `--backend` を除く引数を `engine/sycl/setup_intel.py` に転送します（`terminal/setup.py:9213-9236`, `terminal/setup.py:11414-11417`）。転送先も `setup.py` の `main()` を呼び出します（`engine/sycl/setup_intel.py:594-607`）。ただし、この経路でも `--skip-build` を参照する処理は見つからず、同フラグによるビルド抑止は確認できません。

通常の macOS 委譲経路では `setup.py` が引数を `engine/metal/setup_mac.py` に渡します（`terminal/setup.py:11218-11219`, `terminal/setup.py:9206-9210`）。Metal 側 parser は未知引数を残し、「not used on a Mac」と警告します（`engine/metal/setup_mac.py:372-405`）。この条件では `--skip-build` は抑止フラグとして働かず、未使用引数として扱われます。

## 適用条件と副作用

トップレベル parser が動く経路では受理されますが、ビルド抑止の効果は確認できません。通常の CUDA/HIP 等の処理でビルドを避ける効果、設定ファイル・環境変数との優先順位、または `--build` との特別な相互作用はソースにありません。macOS の通常委譲経路では未使用引数の警告が出ます。ビルド自体の有無は別の条件や `--build` によって決まり、このオプションはそれを変更しません。

## 出力とエラー

`terminal/setup.py` の parser ではこのフラグ固有の警告・エラー・終了コードは定義されていません。macOS の委譲先は未認識の残余引数を警告として出力し、処理を続けます（`engine/metal/setup_mac.py:403-405`）。それ以外の具体的な出力や失敗経路は、このオプション単独の分岐がないため確認できません。

## 根拠

- `terminal/setup.py:11384-11385` — `store_true`、ヘルプ非表示、parser 実行。
- `terminal/setup.py:9513-9542` — 通常のエンジン選択は `a.build` を参照。
- `terminal/setup.py:8413-8427` — update 時の再ビルド指定も `a.build` を使用。
- `terminal/setup.py:9213-9236`, `terminal/setup.py:11414-11417`, `engine/sycl/setup_intel.py:594-607` — SYCL 経路の引数転送。
- `terminal/setup.py:11218-11219`, `terminal/setup.py:9206-9210`, `engine/metal/setup_mac.py:372-405` — macOS の委譲と未知引数警告。
- `docs/cli/README.md:1652-1710` — `source-setup` ルート階層の索引リンクと配置スコープ。
