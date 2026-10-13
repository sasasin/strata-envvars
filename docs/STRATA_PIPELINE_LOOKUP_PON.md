# `STRATA_PIPELINE_LOOKUP_PON`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。

## 役割

`--pipeline-windows 2` の decode loop で、prompt lookup が作った window A の続きから次の window B も作れたときに、B が「直前の A を全採用できる」という推定値 `p_on` を設定します。B の推定値は speculative window の起動判定に使われます。この変数は lookup の使用や lookup window 自体の選択を有効化するものではありません。lookup が選ばれていない場合、B に続く lookup token がない場合、または pipeline decode loop に入らない場合は効果がありません。

## 値と判定

この値の読み取りは `pipe_dbg_env()` 経由で、`STRATA_PIPELINE_DEBUG` が有効なときに限られます。Debug gate が有効なら、未設定時は `0.75`、設定時は `std::atof()` の結果を使います。文字列全体の検証はなく、数値部分の後ろは無視されます。空文字や数値に変換できない文字列は `atof` の結果が `0` となり、数値の先頭部分が使える文字列（例: `0.6junk`）はその数値に変換されます。

| 状態 | `pl_lookup_pon` | lookup から B を作る条件への影響 |
|---|---:|---|
| `STRATA_PIPELINE_DEBUG` が未設定、空文字、または先頭文字が `0` | `0.75`（対象変数を読まず既定値） | 正の既定値として扱う |
| Debug gate 有効、対象変数が未設定 | `0.75` | `> 0` を満たす |
| Debug gate 有効、変換結果が正 | 変換結果 | `> 0` を満たす |
| Debug gate 有効、変換結果が `0` または負 | 変換結果 | B を lookup から作らない |

値の範囲制限や 0〜1 への clamp はありません。したがって `1` より大きい正値も `p_on` に設定されます。Debug gate の値判定は先頭文字だけで、先頭が `0` 以外の設定値（空文字を除く）なら有効です。たとえば `false` は有効、`0anything` は無効です。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が有効であること。無効なら `pipe_dbg_env()` はこの変数について `nullptr` を返し、既定値 `0.75` が使われます。
- `--serve` の layer split が `--pipeline-windows 2` の実行条件を満たし、decode の pipeline 経路が実行されること。`src/program/generate.cpp` の CUDA/HIP 経路は二段以上、SYCL 経路はちょうど二段の split を要求します。pipeline を利用する設定には MTP drafter と `--spec >= 2` も必要です。コード上、HIP は条件を満たす構成で自動選択される経路もあります。
- `--suffix-draft` が正で、対象 window の `seq` が 0 より大きく、suffix lookup の提案があり、最初の lookup token と drafter の先頭予測が一致し、`DraftPolicy::choose()` が lookup を選んでいること。
- lookup window A の後ろに少なくとも1 token (`rest >= 1`) があり、`pl_lookup_pon > 0` で、同じ chain から既に B を作っていないこと。

## 実行時の詳細

Debug gate は `pipe_dbg_env()` 内の関数ローカル `static const bool` です。lookup 値も同じく関数内の `static const float` に保存されるため、最初の評価後にプロセス環境を変えても再評価されません。`STRATA_PIPELINE_DEBUG` が無効のまま初期化された場合、この変数を後から設定しても gate と lookup 値は変わりません。

条件を満たすと `pick_lookup()` は残りの lookup token から B の token 列を設定し、`B.p_on = pl_lookup_pon`、`B.ready = true`、`B.made = true` とします。このとき B の長さは `min(S, rest)` です。`pl_theta`（既定 `0.2`。別の debug 変数 `STRATA_PIPELINE_THETA` で変更可能）と比べ、`B.p_on >= theta` なら、context 上限など追加条件を満たす stage 0 で B を先行実行できます。stage 0 より後の front stage は別条件で B を進められます。したがって正の値を設定しただけで必ず B が stage 0 から実行されるわけではありません。

lookup から B を作らない値（0 以下など）では、その lookup 由来 B は作られません。後段では通常の chain B 作成条件に進みますが、A が lookup window (`A.sfx`) の場合は `make_b()` を呼ばないため、その chain からの通常 B も作られません。B の起動見込みと実際に A の bonus token が一致したかは、pipeline の calibration 集計にも記録されます。

この変数は CUDA/HIP 側 `src/program/generate.cpp` と SYCL 側 `sycl/src/program/generate.cpp` の両方に同じ parse と B 作成条件があります。ソース内の該当箇所および `docs/DETAILS.md` の pipeline 説明には、この変数固有の推奨値や性能測定値は見当たりません。

## 根拠

- `src/program/generate.cpp:251-257`: pipeline debug 環境変数の gate と値の取得。
- `src/program/generate.cpp:3391-3430,7470-7475,11305-11324`: pipeline の CLI 条件、pipeline loop の有効条件と decode 経路。
- `src/program/generate.cpp:11538-11574`: lookup 選択、既定値 `0.75`、B 作成と `p_on` の設定。
- `src/program/generate.cpp:11748-11758,11829-11835`: B の先行実行 gate と `p_on` の calibration。
- `sycl/src/program/generate.cpp:295-297,10769-10805`: SYCL 側の gate と同じ lookup/B 処理。
- `docs/DETAILS.md:173-177` の pipeline 概説と `docs/DETAILS.md:1876-1879` の prompt lookup 説明を照合しました。変数固有の説明・測定値は確認できません。
