# `STRATA_EXPERIMENTAL_SM60`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（2026-11-23 時点）。

## 役割

この環境変数は、Strata のターミナルセットアップ (`terminal/setup.py`) で Pascal（compute capability 6.x）と Volta（7.0）の NVIDIA GPU を利用候補に含める opt-in である。値が有効だと `gpu_problem()` がこれらの GPU を「古すぎる」として除外しなくなり、通常の NVIDIA GPU 候補選択や既存モデルの起動時の GPU 検査を通せる。セットアップは対象カードを選ぶと原則 CUDA 12 エンジンを選ぶ。環境変数だけで GPU を選択したり、モデルの設定・実行中エンジンを書き換えたりはしない。`terminal/setup.py:2001-2005, 2134-2140, 11565-11580`。

同名はエンジン側では CMake オプション／コンパイルマクロとして使われるが、実行時にエンジンがこの名前を `getenv` で読む箇所はない。セットアップが `-DSTRATA_EXPERIMENTAL_SM60=ON` を CMake に渡すことで、CUDA ビルドに古い世代向けコードを含める。CUDA CMake オプションの既定値は `OFF` で、ON のとき `STRATA_EXPERIMENTAL_SM60=1` をコンパイル定義にする。`engine/cmake/backends/cuda.cmake:28, 47-57, 76-80`。

## 値と判定

`os.environ.get("STRATA_EXPERIMENTAL_SM60", "").strip() == "1"` で文字列全体を比較する。未設定は既定の空文字、空文字も無効。前後の空白だけは除去されるが、大文字小文字変換や数値変換はしない。したがって `1` と ` 1 ` は有効、`0`、`01`、`true`、`1x`、`1 0`、空文字は無効である。`terminal/setup.py:2001-2005, 2032-2041`。

| 条件 | unset / 無効値 | 有効値 | 判定結果 |
|---|---|---|---|
| `terminal/setup.py` の NVIDIA GPU 判定 | unset、空、`0`、`true` 等 | `1`（前後空白可） | 有効時、Pascal/Volta を利用可能候補として扱う。ただし別の opt-in 条件でも同じ扱いになる。`terminal/setup.py:2001-2005, 2032-2049, 2134-2140` |
| CUDA エンジンを CMake で構成 | この環境変数自体は CMake のオプション値ではない。CMake オプション `STRATA_EXPERIMENTAL_SM60` の既定は `OFF` | セットアップが `-DSTRATA_EXPERIMENTAL_SM60=ON` を渡す | CUDA を有効にしたビルドでのみオプションが宣言・適用され、ON ならコンパイル定義を付ける。`engine/cmake/backends/cuda.cmake:24-28, 76-80` |

## 有効になる条件

- セットアップが NVIDIA GPU を評価する経路で、GPU の compute capability が 6.0〜7.0（コード上の `60 <= arch <= 70`）であること。Maxwell（5.x）はこの環境変数の対象外で、セットアップの `gpu_problem()` は利用不可とする。通常の macOS セットアップは `main()` 冒頭で `mac_setup()` に分岐するため、この NVIDIA 判定経路を通らない。`terminal/setup.py:2008-2014, 2134-2140, 11218-11219`。
- この変数が有効でなくても、Pascal/Volta を `--gpu` / `--gpus` で指定したとき、`--cuda 12` のとき、または利用可能な新しい NVIDIA GPU がなく、利用可能な AMD GPU もないときは `old_gpus_opt_in()` が同じ opt-in 状態を返す。変数が有効なら、これらの条件や新しい NVIDIA/AMD GPU の有無にかかわらず opt-in 理由として優先される。`terminal/setup.py:2032-2049, 11565-11570`。
- `--backend hip` を指定するとセットアップは AMD/HIP 経路を選び、NVIDIA の旧世代対応はその実行経路を有効にしない。環境変数による GPU 判定自体は行われるが、旧 NVIDIA GPU の案内警告は `a.backend != "hip"` の場合に限られる。`terminal/setup.py:11565-11618`。
- 自動選択では、選ばれた GPU 群に sm_75 未満が含まれると `cuda_choice()` が CUDA 12 を選ぶ。`--cuda 13` は明示選択として優先され、古い GPU にコードがない旨の理由を返す。`--cuda` の既定値は別の環境変数 `STRATA_CUDA` または `None` であり、`STRATA_EXPERIMENTAL_SM60` がそれを上書きすることはない。`terminal/setup.py:2091-2109, 11228-11231, 11673-11680`。
- セットアップがローカルでエンジンをビルドする場合、`engine_defs()` は arch が 75 未満、または選択 toolkit が 12 のときに CMake オプションを ON にする。`build_engine()` は CUDA を有効にして CMake を呼び、この定義を渡す。CUDA 12.x toolkit が必要で、Pascal/Volta を含む低い arch でオプションが OFF の場合は CMake が構成エラーにする。`terminal/setup.py:6531-6537, 6786-6789, 6857-6863`; `engine/cmake/backends/cuda.cmake:47-57`。
- CMake 側の実行時 compute capability 下限は、このマクロが有効な CUDA ビルドでは 6.0、無効なビルドでは 7.5。したがって有効化しても 6.0 未満のカードを実行可能にするわけではない。`engine/src/core/device.cu:309-322`。

## 実行時の詳細

セットアップの `main()` は PC の GPU を列挙し、`old_gpus_opt_in()` の結果をプロセス内の `OLD_GPUS` に保存する。その後 `gpu_problem()` と GPU 候補一覧 (`gpu_table()`) が `experimental_sm60()` を参照するため、有効値は旧世代カードの利用可否表示・選択に反映される。起動時には保存済みモデルの CUDA toolkit も `old_gpus_opt_in()` に渡される。`terminal/setup.py:1985-2005, 2157-2162, 8550-8553, 11560-11580`。

環境変数は関数呼び出しごとに `os.environ.get()` され、`experimental_sm60()` に static cache はない。一方、`OLD_GPUS` は同一セットアッププロセス内で opt-in 理由を保持する。別プロセスとしてセットアップを再実行すれば、そのプロセスの環境を読み直す。エンジン実行時に同名環境変数を再読込して機能を切り替える処理は確認できない。`terminal/setup.py:2001-2005, 2032-2041, 11565-11570`。

ローカルビルドでは、セットアップが選んだ arch/toolkit に応じて CMake 定義を生成する。定義が入った CUDA エンジンは、Pascal/Volta 対応コードを含み、実行時デバイス検査の下限も 6.0 になる。プリビルトの CUDA 12 エンジン取得経路もあるため、環境変数が有効だから常にその場でコンパイルするわけではない。`terminal/setup.py:6786-6789, 6818-6863, 9108-9116`; `engine/cmake/backends/cuda.cmake:76-80`; `engine/src/core/device.cu:311-322`。

## ログと測定値

セットアップで旧 GPU の opt-in が成立し、HIP backend ではない場合、次の警告を出す（`OLD_GPUS` の理由文字列は `STRATA_EXPERIMENTAL_SM60=1`）。

```text
older NVIDIA GPUs (Pascal / Volta) can be used (STRATA_EXPERIMENTAL_SM60=1): experimental, through a second engine built with CUDA 12 (docs/OLDER_GPUS.md)
```

無効値そのものに対する専用警告・エラーはない。ローカル CUDA 構成で arch が 75 未満なのに CMake オプションが OFF なら、CMake は `Strata needs an NVIDIA GPU ...` で始まる fatal error を出す。CUDA 12.x toolkit が見つからない場合、セットアップは `the experimental CUDA 12 engine ... is compiled here ...` という理由を付けて停止する。`terminal/setup.py:6531-6537, 11565-11570`; `engine/cmake/backends/cuda.cmake:53-57`。

## 根拠

- `terminal/setup.py:2001-2005, 2032-2049`: 環境値の判定、他の opt-in 条件と優先順位。
- `terminal/setup.py:2134-2140, 2157-2162`: GPU 利用可否と候補表示。
- `terminal/setup.py:2091-2109, 11228-11231, 11673-11680`: CUDA toolkit の既定選択・CLI 優先・警告。
- `terminal/setup.py:11560-11580, 8550-8553`: セットアップおよび既存モデル起動時の評価と表示。
- `terminal/setup.py:6531-6537, 6786-6789, 6857-6863, 9108-9116`: toolkit 要件、CMake 定義、ローカルビルドとプリビルト取得。
- `engine/cmake/backends/cuda.cmake:24-28, 47-80`; `engine/src/core/device.cu:309-322`: CMake オプション、compile definition、実行時 GPU 下限。
