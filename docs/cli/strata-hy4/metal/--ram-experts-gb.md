# `strata-hy4-metal --ram-experts-gb`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4-metal`（Metal） |
| オプション | `--ram-experts-gb` |
| 別名 | なし |
| 値 | 次のコマンドライン引数を1つ消費する。数値への変換や値域検証はない。 |

## 役割

Metal runner では RAM 上の expert 容量を設定しない。このオプションは受理されるが、値を設定へ反映せず、未使用であることを標準エラーへ出力する。

## 使い方

```sh
strata-hy4-metal --model model.strata --tokens prompt.ids --ram-experts-gb 16
```

この例では `16` は容量として適用されず、未使用の警告に表示される。実行には有効なモデルと token ファイルが必要。

## 値と既定値

オプションの直後の引数を1つ読み取り、数値変換せず警告文へ埋め込む。したがって数値形式・単位・範囲の検証はなく、既定値も設定されない。省略時はこのオプションによる処理はない。複数回指定すると、その都度1引数を消費して警告を出す。

引数を取る処理は `argv[++i]` で行われ、末尾指定を検査する境界チェックは parser にない。値を省略した場合の正常なエラー処理はソースから確認できないため、末尾指定は避けること。また、次の引数が別オプションでも値として消費され、そのオプションは parser に渡らない。

## 実行時の動作

引数解析時に `[args] --ram-experts-gb <値>: not used by the Metal runner` を標準エラーへ出力する。警告後も解析を続け、値を RAM 予算やモデル設定へ転送しない。値の違いによる Metal の expert 配置変更はない。

## 適用条件と副作用

対象は `strata-hy4-metal` の Metal runner。副作用は警告の標準エラー出力と、値として次の引数を消費すること。モデル指定がない場合は通常の必須引数確認に進み、usage を標準エラーへ出して終了コード `2` となる。このオプション自体の警告は終了させない。

## 出力とエラー

- オプション指定時: `[args] --ram-experts-gb <値>: not used by the Metal runner` を stderr に出す。
- 未知の引数: `ERR unknown flag <引数>` を stdout、`unknown arg <引数>` を stderr に出して終了コード `2`。
- `--ram-experts-gb` の値を省略した場合: parser に境界チェックがないため、定義されたエラー表示・終了コードは確認できない。

## 根拠

- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1488-1506` — Metal CLI の引数解析ループと、次の argv を無条件に読む `nxt`。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1603-1609` — `--ram-experts-gb` を未使用扱いにする分岐、stderr 出力、未知引数の stdout/stderr と終了コード。
- `engine/src/hy4flash/metal/hy4_metal_main.cpp:1611-1613` — model 未指定時の usage と終了コード `2`。
- `docs/cli/README.md:1358-1360,1425` — `strata-hy4` の Metal scope と、本オプションの索引リンク。
