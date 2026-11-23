# `strata-inkling-sycl --ep-split`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl` |
| オプション | `--ep-split` |
| 別名 | なし |
| 値 | 浮動小数点として `atof` で変換される値。EP 有効時に `0.1..0.9` へ clamp される |

## 役割

二つの SYCL GPU で Expert Parallelism（EP）を使う場合、expert を GPU 1 側へ優先配置する割合を指定する。これは VRAM 容量の分割比そのものではなく、expert のハッシュ値から優先 GPU を選ぶ基準である。GPU 1 の VRAM 予算に収まらない expert は GPU 0 側へ回され、そちらにも収まらなければホスト側に置かれるため、最終的な配置割合は指定値と一致するとは限らない（`engine/src/inkling2/sycl/ink_sy_common.h:837-874`）。

## 使い方

```sh
# GPU 0 と GPU 1 の二台を要求し、GPU 1 側への優先配置を 65% にする
strata-inkling-sycl --model model.strata --gpus 0,1 --ep-split 0.65
```

`--ep-split` は `--gpus` / `--devices` による複数 GPU 要求と組み合わせて使う。環境変数 `IK2_EP_SPLIT` も設定されていて、その値が有効範囲なら環境変数がこの CLI 値を上書きする（詳細は [`IK2_EP_SPLIT`](../../../envvars/IK2_EP_SPLIT.md)）。

## 値と既定値

- 既定値は `0.5`（`engine/src/inkling2/sycl/ink_sy_main.cpp:103-108`）。
- 引数は `std::atof` で変換され、入口で範囲検証やエラー報告はされない。数値として読める接頭部分があればその値に変換され、数値として読めない文字列は通常 `0` になる。複数回指定した場合は引数解析で最後に現れた値が残る（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-145`）。
- 値が末尾で省略された場合、引数取得関数 `need()` は空文字列を返し、`atof("")` の結果 `0` が使われる。省略位置の次に別の引数がある場合は、その引数を値として消費する。モデル読込時に `0` は `0.1` へ clamp される（同 `:112-114,142`; `engine/src/inkling2/sycl/ink_sy_common.h:784-789`）。
- 明示値が `0.1` 未満なら `0.1`、`0.9` 超なら `0.9` になる。オプション値の拒否や範囲外警告はない（同 `ink_sy_main.cpp:142`; `ink_sy_common.h:784-789`）。
- 起動時に `IK2_EP_SPLIT` が空でなく設定されていると、その値も `atof` で変換される。変換結果が厳密に `0 < v < 1` の場合だけ CLI 値を上書きし、そうでなければ CLI 値を維持する（`engine/src/inkling2/sycl/ink_sy_main.cpp:146-149`）。

## 実行時の動作

引数解析後、入口は `ep_split` を `InkSyModel::load` に渡す（`engine/src/inkling2/sycl/ink_sy_main.cpp:142-148,183`）。load は受け取った値を `std::clamp(req_ep_split, 0.1, 0.9)` で制限する。その後、二 GPU EP の初期化が成功した場合に限り、expert ID と layer index から作るハッシュ値を閾値と比較し、`ep_split` の割合に相当する expert を GPU 1 優先として扱う（`engine/src/inkling2/sycl/ink_sy_common.h:784-789,844-865`）。VRAM 予算によって優先先から別 GPU またはホストへ配置先が変わる。

EP の初期化は `--gpus` / `--devices` で二台以上を要求した場合に試みられる。二台目の SYCL queue を作成でき、二台目の VRAM 予算が正なら EP が有効になる。二台目の初期化で SYCL 例外が起きた場合や二台目の VRAM 予算が正でない場合、コードは二 GPU を使わない経路へ進む。二台以上を要求しても可視 GPU が一台だけの場合も single-GPU 実行へ進む（`engine/src/inkling2/sycl/ink_sy_common.h:792-834`）。EP が無効なら `ep_split` は保持されても配置処理では参照されず、expert は GPU 0 の予算を先に使い、残りをホスト側へ置く（同 `:844-874`）。

`--info` 経路は model の probe 後に load より前で終了するため、この値による EP 配置は行わない（`engine/src/inkling2/sycl/ink_sy_main.cpp:171-183`）。

## 適用条件と副作用

- 対象は SYCL 版 `strata-inkling-sycl` の `.strata` モデル読込経路である。索引上の CUDA/HIP 版および Metal 版とは別 scope（`docs/cli/README.md:1509-1592`）。
- 二台目の GPU と正の VRAM 予算を使った EP 初期化が成立しなければ、指定値による分割は適用されない。split は起動時のモデルロードで参照され、リクエストごとに読み直す処理は確認できない（`engine/src/inkling2/sycl/ink_sy_common.h:792-835,837-880`）。
- 有効化されると、モデル expert のデータが GPU 0、GPU 1、またはホスト側へ配置される。GPU 1 に一つも expert が配置されなかった場合は EP を無効化し、二台目 queue を破棄する（同 `:876-880`）。

## 出力とエラー

- 有効な二 GPU EP でモデルの load が完了すると、stderr の `[ink_sycl] loaded ... Dual-GPU EP2 ... split=...` 行に clamp 後の値が表示される。single-GPU 経路では通常の単一デバイス load 情報が表示され、split 値は表示されない（`engine/src/inkling2/sycl/ink_sy_common.h:971-987`）。
- 二台目 queue 作成時の SYCL 例外は stderr に理由付きで記録され、single-GPU へ fallback する。要求 GPU 数に対して可視 GPU が足りない場合も stderr にメッセージを出して single-GPU へ進む（同 `:827-834`）。
- `.strata` の open や header 読込など model load が失敗すると `load` が理由を返し、入口は stderr に `[ERROR] <理由>` を出して終了コード `1` を返す（`engine/src/inkling2/sycl/ink_sy_common.h:664-670`; `engine/src/inkling2/sycl/ink_sy_main.cpp:183`）。split 値自体の不正を理由にしたエラー経路は確認できない。

## 根拠

- parser、既定値、環境変数による上書き、load への引き渡し: `engine/src/inkling2/sycl/ink_sy_main.cpp:103-149,166-183`。
- load 引数、clamp、二 GPU EP の有効条件と fallback: `engine/src/inkling2/sycl/ink_sy_common.h:660-665,784-834`。
- split による expert の優先配置、容量不足時の代替先、EP 無効化条件: `engine/src/inkling2/sycl/ink_sy_common.h:837-880`。
- load 成功時の診断出力と peer expert table の割当失敗: `engine/src/inkling2/sycl/ink_sy_common.h:962-989`。
- CLI tool ID・SYCL parser scope・索引リンク: `docs/cli/000_cli_tools.md:7-13`; `docs/cli/README.md:1572-1592`（索引の定義は調査対象との同一 commit SHA と調査日を照合して使用）。
