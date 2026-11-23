# `strata-inkling-sycl --vram-experts-gb`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-inkling` |
| コマンド | `strata-inkling-sycl`（SYCL 実行ファイル、root） |
| オプション | `--vram-experts-gb` |
| 別名 | なし |
| 値 | 数値 `G`。GiB 換算の VRAM expert 予算として扱う。 |

## 役割

Inkling-2-Mini の SYCL 実行ファイルで、expert 本体を VRAM に置くための予算を指定する。未指定時の自動予算を置き換え、その予算内で優先順に配置できた expert を GPU に載せ、残りを host USM に置く。指定値は VRAM の確保量そのものではなく配置予算の上限であり、モデルと expert のサイズによって実際に載る量は変わる。

## 使い方

```sh
strata-inkling-sycl --model ./model.strata --vram-experts-gb 4
```

## 値と既定値

- 値は次の argv 要素から読み、`std::atof` で `double` に変換する。型・範囲の検証や parse error は実装されていない。数値として解釈できない文字列は `atof` の結果 `0` となり、明示的な 0 と同様に VRAM 予算を 0 にする。オプションを複数回指定した場合は、ループ中に代入されるため最後の値が残る（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-114,143`）。
- 既定値は `-1.0`。ローダーは値が `0` 以上のときだけ自動算出予算を上書きするため、負数は自動予算を使う。`0` は VRAM に expert を割り当てない指定となる（`engine/src/inkling2/sycl/ink_sy_main.cpp:107-109,143`、`engine/src/inkling2/sycl/ink_sy_common.h:772-782`）。
- 非負の値は `値 × 1024³` バイトに変換される。したがって引数名の `GB` にかかわらず、コード上の換算単位は 2 進の GiB である（`engine/src/inkling2/sycl/ink_sy_common.h:780-782`）。

## 実行時の動作

通常のロードでは、まず GPU メモリ容量、既に確保済みの device memory、容量に応じた予約量から自動 VRAM 予算を計算する。明示値が 0 以上なら GPU 0 の予算を指定値に置き換える（`engine/src/inkling2/sycl/ink_sy_common.h:772-782`）。

モデルの expert 優先順に走査し、各 expert の本体サイズが残予算内に収まれば VRAM、収まらなければ host USM に分類する。したがって予算を増やしても、指定量ぴったりの VRAM を使うわけではない（`engine/src/inkling2/sycl/ink_sy_common.h:837-875`）。ロード完了時は stderr の `[ink_sycl] loaded ... VRAM experts=...` ログに、実際に VRAM に載った件数・容量と host 件数が出る（`engine/src/inkling2/sycl/ink_sy_common.h:971-989`）。

## 適用条件と副作用

- `--info` を指定した場合は model metadata を probe して表示した後、ロード処理より前に終了する。そのため同時に指定した本オプションは VRAM 配置に適用されない（`engine/src/inkling2/sycl/ink_sy_main.cpp:173-183`）。
- `--gpus` で Dual-GPU EP が有効な場合、GPU 0 は指定値をそのまま予算にする一方、GPU 1 は「GPU 1 の総 VRAM − 768 MiB」と指定値の小さい方を予算にする。各 GPU の予算内で expert を配置する（`engine/src/inkling2/sycl/ink_sy_common.h:792-829,837-875`）。
- GPU 0 の明示予算は自動計算時の予約や空き容量で再度上限化されない。予算を大きく指定すると device allocation に失敗し得る。GPU slab の割当失敗時は `dalloc` が `out of device memory` として device error 経路で終了する。GPU 1 slab の失敗は `peer GPU1 slab OOM` を設定してロード失敗を返す（`engine/src/inkling2/sycl/ink_sy_common.h:228-238,906-914,956-959`）。
- 負数で自動値に戻せるが、非数や極端な値に対する個別の検証・エラー処理は parser にない。こうした入力の挙動はコード上で安全な仕様として定められていないため、ここでは値の範囲として保証しない（`engine/src/inkling2/sycl/ink_sy_main.cpp:112-114,143`）。

## 出力とエラー

モデルのロードが通常の `false` 失敗を返した場合、CLI は stderr に `[ERROR] <理由>` を出し、終了コード 1 を返す（`engine/src/inkling2/sycl/ink_sy_main.cpp:183`）。device allocation の失敗は上記の `exit_device_error` 経路となる（`engine/src/inkling2/sycl/ink_sy_common.h:228-238`）。

## 根拠

- `engine/src/inkling2/sycl/ink_sy_main.cpp:101-114,125-145` — standalone SYCL CLI の引数処理、既定値、数値変換、別名なし。
- `engine/src/inkling2/sycl/ink_sy_main.cpp:166-183` — model 必須時の usage、`--info` の早期終了、モデルロードと失敗出力。
- `engine/src/inkling2/sycl/ink_sy_common.h:772-782,837-875` — 自動予算、明示予算の適用、優先順に基づく VRAM / host 配置。
- `engine/src/inkling2/sycl/ink_sy_common.h:792-835` — Dual-GPU 条件と GPU 1 予算の上限。
- `engine/src/inkling2/sycl/ink_sy_common.h:906-959,971-989` — slab 確保・読込エラーとロード結果ログ。
- `docs/cli/README.md:1572-1592` — `strata-inkling-sycl` のコマンド階層と対象オプションの索引登録。
