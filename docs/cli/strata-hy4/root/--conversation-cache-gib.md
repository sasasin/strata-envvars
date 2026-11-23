# `--conversation-cache-gib`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-hy4` |
| コマンド | `strata-hy4`（root。`--serve` と組み合わせて使用） |
| オプション | `--conversation-cache-gib` |
| 別名 | なし |
| 値 | GiB 単位の数値。parser は `atof` で `double` に変換する |

## 役割

`--serve` の会話キャッシュがディスク上で使う容量上限を指定する。保存先を有効にするには `--conversation-cache-dir` も必要で、ここで設定した上限を超えると、最終利用時刻が最も古いキャッシュから削除する。これは Hy4-Flash の CUDA/HIP root CLI で確認した挙動であり、Metal / SYCL の parser にはこのオプションがありません。

## 使い方

```sh
# CUDA/HIP の serve で、./hy4-cache に最大 40 GiB の会話キャッシュを置く
strata-hy4 --serve --native model.strata --conversation-cache-dir ./hy4-cache --conversation-cache-gib 40
```

## 値と既定値

- 省略時は `40.0` GiB。CLI の初期値と `ServeOpts` の初期値はいずれも `40.0`。
- 引数は `atof` で読み取られ、明示的な数値形式・範囲の検証はありません。重複指定時は引数走査中の後の値が採用されます。
- 内部では GiB 値に `1073741824.0` を掛けて `uint64_t` のバイト予算にします。予算が 0 ならキャッシュ初期化は失敗扱いとなり、キャッシュは無効になります。
- 負数、非数、範囲外などの入力について、parser に専用の拒否・補正処理はありません。浮動小数値から符号なし整数への変換結果を含め、そうした入力の動作はこの調査では確定しません。
- 値を省略すると `ERR --conversation-cache-gib needs a value` を stdout に出し、終了コード 2 で終了します。

## 実行時の動作

root parser は値を `cc_gib` に保存し、`--serve` 分岐で `ServeOpts.cc_gib` に渡します。serve 側は `--conversation-cache-dir` が空でない場合に限り、保存先・予算・最小トークン数・モデルパスを使ってキャッシュを初期化します。したがって、このオプションだけを指定してもキャッシュは有効になりません。`--serve` を指定しない実行経路では値は serve 設定へ渡されず、使われません。

初期化に成功すると、指定ディレクトリを作成し、そこにある互換キャッシュを読み込みます。serve 中に会話を退避すると `.h4cc` ファイルとして保存し、合計サイズが予算を超えた場合は最終利用時刻が最も古いものから削除します。同一内容のキャッシュファイルは置き換えられ、既存の同一ファイルが削除されてから一時ファイルが改名されます。プロンプト処理でキャッシュを復元できるときは保存済み状態を読み戻します。

## 適用条件と副作用

- 対象は `engine/src/hy4flash/run/hy4_main.hip.cpp` の CUDA/HIP root parser と同じ実行ファイルの serve 経路です。`--serve` と空でない `--conversation-cache-dir` の両方が必要です。
- 初期化時に保存先ディレクトリを作成し、既存の `.tmp` ファイルを削除します。モデル名、サイズ、レイヤー数、リング設定などが現在の実行条件に合わない `.h4cc` は無視されます。
- 退避の対象は設定された最小トークン数以上の会話です。要求に画像が含まれる場合、その要求の会話キャッシュ探索・退避を行いません。
- キャッシュはディスク書き込みと削除を行います。予算は保存済みキャッシュの総バイト数に対する上限です。
- `--session-reuse` がなくてもキャッシュが有効なら serve の再利用フラグが有効になります。

## 出力とエラー

- キャッシュを初期化できない場合、stderr に `[convcache] off: cannot use <dir>` を出して serve 自体はキャッシュ無効で続行します。初期化はディレクトリ作成、モデルファイルサイズ取得、レイヤー数確認などに失敗すると `false` を返します。
- 起動時は stderr に保存先、読み込んだ会話数、現在量と予算などを出します。退避・復元・予算超過による削除も stderr に記録されます。
- 退避ファイルを書けない場合や書き込み・改名に失敗した場合は stderr に失敗を記録し、その退避を失敗として返します。
- 値自体に対する専用の validation error は確認できません。HIP メモリ操作の失敗は共通 `HCK` マクロ経由で stderr にエラーを出し、終了コード 3 で終了します。

## 根拠

- `engine/src/hy4flash/run/hy4_main.hip.cpp:357-359` — root CLI の `cc_gib` 初期値。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:375-383,445-447` — 引数走査、値なし時のエラーと終了コード、`atof` による parser 登録。
- `engine/src/hy4flash/run/hy4_main.hip.cpp:544-567` — `--serve` 時に `ServeOpts` へ値を渡す箇所。
- `engine/src/hy4flash/run/hy4_serve.hip.h:43-53,365-370` — serve 設定の初期値、保存先が空でないときだけ初期化する条件、初期化失敗時の警告と再利用状態。
- `engine/src/hy4flash/run/hy4_convcache.h:71-103` — GiB からバイトへの換算、0 予算の無効化、ディレクトリ作成・モデル検査・初期走査。
- `engine/src/hy4flash/run/hy4_convcache.h:165-166,191-219,221-235` — 退避条件、一時ファイル書き込みと置き換え、エラー出力、予算適用後の退避ログ。
- `engine/src/hy4flash/run/hy4_convcache.h:305-327` — キャッシュ総量と最終利用時刻に基づく削除。
- `engine/src/hy4flash/run/hy4_serve.hip.h:470-489,602-608` — 画像要求を除くキャッシュ探索・復元、serve 終了時の退避。
- `engine/src/hy4flash/run/hy4_gpu_model.hip.h:27-34` — HIP エラー時に stderr を出し終了コード 3 で終了する共通処理。

