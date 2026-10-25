# `STRATA_RAM_ADAPT_QUEUE`

調査対象: Strata `main` の HEAD `011c9e600a93bbc9fd451c563501b5831c32bbca`（2026-10-22 時点）。外部ライブラリの環境変数は対象外。

## 役割

`STRATA_RAM_ADAPT2` の resident RAM 適応で、ファイルからの読み込みを先行させるステージ済み昇格ジョブの最大保持数を指定します。読み込み worker が処理中の job や読み込み完了後に次の window 境界で install される job も、この上限に数えられます。値を小さくすると未処理 job が残っている間に新しい昇格を受け付けにくくなり、大きくすると保持できる job 数が増えます。RAM の大きさや一 window あたりの昇格数を直接指定する変数ではありません。

## 値と判定

読み取り箇所は `FileExpertSource::ram_stage()` のローカル `static const size_t cap` 一つです。環境変数が未設定なら上限は `64`。設定されていれば `std::atoi()` で整数変換し、`std::max(1, ...)` で最低 `1` にした値を使います。

| 設定 | `atoi` の結果 | job 上限 |
|---|---:|---:|
| 未設定 | — | 64 |
| `8`、`8tail` | 8 | 8 |
| 空文字、`text`、`0`、負数 | 0 以下 | 1 |
| `  +3tail` | 3 | 3 |

`atoi` は先頭の空白と符号を許し、数値の後ろに続く文字列を検査しません。数値として解釈できる先頭部分がない文字列は 0 となり、上限は 1 になります。コードは最大値を別途 clamp していません。読み取り値は初回の `ram_stage()` 呼び出し時に static 変数へ保存されるため、その後プロセス内で環境を書き換えても再評価されません。

根拠: `src/core/expert_source.cpp:4370-4380`。

## 有効になる条件

この値が使われるのは、decode window 境界の処理で次の条件が成立し、`src.ram_stage()` が呼ばれる経路です。

- `STRATA_RAM_ADAPT` の変換結果が 1 以上で、`STRATA_RAM_ADAPT2` も有効。
- 最初の window ではなく、adaptive usage が存在し、pending の adaptive swap がない。
- 非同期 adaptive job がないか idle。
- resident RAM copy が利用可能で、単一 GPU、peer device なし、remote expert なし、batch 無効（`o.batch == 0`）。
- 候補となる expert の組が選ばれる。組の総数は `STRATA_RAM_ADAPT` の値でも制限される。

`STRATA_RAM_ADAPT2` が無効なら、`STRATA_RAM_ADAPT` の同期経路で `replace_resident()` が使われ、`STRATA_RAM_ADAPT_QUEUE` は読み取られません。`STRATA_RAM_ADAPT2` が有効でも上の条件が成立しない window では queue 上限の効果はありません。

根拠: `src/program/generate.cpp:8276-8283,14794-14807,14872-14877,14878-14899`。

## 実行時の詳細

`ram_stage()` は mutex の下で `ram_jobs_.size() >= cap` を検査し、満杯なら `false` を返します。呼び出し側は `true` の場合だけ、その window で stage できた件数を加算します。満杯を含む stage 失敗そのものについて、ここから専用ログやエラーは出ません。適用時には同一 layer の候補 expert が既に別 job に含まれる場合も拒否されます。

job は I/O worker が一つずつファイルから読みます。完了または失敗した job も `ram_jobs_` に残り、次の適用可能な window 境界で `ram_install()` が state 2 以上の job を取り出して消去するまで `size()` に含まれます。従って上限は単なる待ち行列の未処理要素数ではなく、処理中・完了済みを含む未回収 job 数です。読み込みに成功した job は install 時に RAM copy へ反映されますが、その間に GPU tier が対象 expert を取った場合などは install を skip します。

server 終了時、`STRATA_RAM_ADAPT2` が有効なら累積の read / installed / skipped 件数が stderr に出ます。この集計は queue 上限で拒否された件数を個別に表示しません。

根拠: `src/core/expert_source.cpp:4380-4392,4402-4454`、`src/program/generate.cpp:14805-14815,14872-14877,15368-15372`。

## 文書との照合

`docs/DETAILS.md:172-181` は `STRATA_RAM_ADAPT` の同期 resident RAM 適応を説明しています。今回の HEAD には `STRATA_RAM_ADAPT2` の staged read 経路と `STRATA_RAM_ADAPT_QUEUE` の実装がありますが、同資料にはこの queue 上限の説明や測定値は見当たりません。性能への影響は値だけから推定できないため記載していません。
